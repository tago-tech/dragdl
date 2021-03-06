# ClassifierTask define.
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import collections
import contextlib
import time
import multiprocessing
import copy

import time
import numpy as np
import paddle.fluid as fluid
from visualdl import LogWriter


import paddlehub as hub
from paddlehub.common.paddle_helper import dtype_map, clone_program
from paddlehub.common.utils import mkdir, to_list
from paddlehub.finetune.checkpoint import load_checkpoint, save_checkpoint
from paddlehub.finetune.evaluate import chunk_eval, calculate_f1
from paddlehub.finetune.config import RunConfig


class RunState(object):
    def __init__(self, length):
        self.run_time_begin = time.time()
        self.run_step = 0
        self.run_examples = 0
        self.run_results = [0] * length
        self.run_time_used = 0
        self.run_speed = 0.0

    def __add__(self, other):
        self.run_step += other.run_step
        self.run_examples += other.run_examples
        for index in range(len(self.run_results)):
            self.run_results[index] += other.run_results[index]
        return self

    def update(self):
        self.run_time_used = time.time() - self.run_time_begin
        self.run_speed = self.run_step / self.run_time_used
        return self

class RunEnv(object):
    def __init__(self):
        self.current_epoch = 0
        self.current_step = 0
        self.main_program = None
        self.start_program = None
        self.main_program_compiled = None
        self.py_reader = None
        self.reader = None
        self.loss = None
        self.labels = None
        self.metrics = None
        self.is_inititalized = False
        self.UNG = copy.deepcopy(fluid.unique_name.generator)

    def __setattr__(self, key, value):
        self.__dict__[key] = value

    def __getattr__(self, key):
        return self.__dict__[key]

class BasicTask(object):
    def __init__(self,
                 feed_list,
                 data_reader,
                 main_program=None,
                 startup_program=None,
                 config=None,
                 logger=None):

        self.logger = logger
        # base item
        self._base_data_reader = data_reader
        self._base_feed_list = feed_list
        if main_program is None:
            self._base_main_program = clone_program(
                fluid.default_main_program(), for_test=False)

        else:
            self._base_main_program = clone_program(
                main_program, for_test=False)
        if startup_program is None:
            self._base_startup_program = clone_program(
                fluid.default_startup_program(), for_test=False)
        else:
            self._base_startup_program = clone_program(
                startup_program, for_test=False)
        self.is_checkpoint_loaded = False
        self._base_compiled_program = None

        # run config
        self.config = config if config else RunConfig()
        self.place = self.places[0]
        self.device_count = len(self.places)

        if self.config.use_data_parallel:
            if not self.config.use_pyreader and self.config.batch_size < self.device_count:
                self.logger.warning(
                    "Batch size({}) is less than the count of devices({}), which is not allowed in current Paddle versions"
                    .format(self.config.batch_size, self.device_count))
                self.logger.warning("Batch size automatically adjusted to {}".format(
                    self.device_count))
                self.config._batch_size = self.device_count

        self.exe = fluid.Executor(place=self.place)
        self.build_strategy = fluid.BuildStrategy()
        if self.config.enable_memory_optim:
            self.build_strategy.memory_optimize = True
        else:
            self.build_strategy.memory_optimize = False

        # log item
        if not os.path.exists(self.config.checkpoint_dir):
            mkdir(self.config.checkpoint_dir)
        vdl_log_dir = os.path.join(self.config.checkpoint_dir, "vdllog")
        self.log_writer = LogWriter(vdl_log_dir, sync_cycle=1)

        # run environment
        self._phases = []
        self._envs = {}
        self._predict_data = None

        # set default phase
        self.enter_phase("train")

        

    @contextlib.contextmanager
    def phase_guard(self, phase):
        self.enter_phase(phase)
        yield
        self.exit_phase()

    def enter_phase(self, phase):
        if phase not in ["train", "val", "dev", "test", "predict", "inference"]:
            raise RuntimeError()
        self._phases.append(phase)

    def exit_phase(self):
        self._phases = self._phases[:-1]

    def init_if_necessary(self):
        if not self.is_checkpoint_loaded:
            self.is_checkpoint_loaded = True
            if not self.load_checkpoint():
                self.exe.run(self._base_startup_program)

    def _build_env(self):
        if self.env.is_inititalized:
            return

        self._build_env_start_event()
        self.env.is_inititalized = True
        self.env.main_program = clone_program(
            self._base_main_program, for_test=False)

        self.env.startup_program = fluid.Program()
        with fluid.program_guard(self.env.main_program,
                                 self._base_startup_program):
            with fluid.unique_name.guard(self.env.UNG):
                self.env.outputs = self._build_net()
                if self.is_train_phase or self.is_test_phase:
                    self.env.labels = self._add_label()
                    self.env.loss = self._add_loss()
                    self.env.metrics = self._add_metrics()

        if self.is_predict_phase or self.is_test_phase:
            self.env.main_program = clone_program(
                self.env.main_program, for_test=True)
            hub.common.paddle_helper.set_op_attr(
                self.env.main_program, is_test=True)

        if self.config.use_pyreader:
            t_program = fluid.Program()
            with fluid.program_guard(t_program, self.env.startup_program):
                self.env.py_reader = fluid.layers.py_reader(
                    capacity=64,
                    shapes=[var.shape for var in self.feed_var_list],
                    dtypes=[dtype_map[var.dtype] for var in self.feed_var_list],
                    lod_levels=[var.lod_level for var in self.feed_var_list],
                    use_double_buffer=False)

                feed_var_list = self.feed_var_list
                py_vars = fluid.layers.read_file(self.env.py_reader)
                py_vars = to_list(py_vars)
                input_dict = {
                    feed_var_list[index].name: py_var
                    for index, py_var in enumerate(py_vars)
                }

                hub.connect_program(
                    pre_program=t_program,
                    next_program=self.env.main_program,
                    input_dict=input_dict,
                    need_log=False)

            self.env.main_program = t_program
            if not self.is_predict_phase:
                self.env.loss = self.env.main_program.global_block().vars[
                    self.env.loss.name]
                metrics_name = [var.name for var in self.env.metrics]
                self.env.metrics = [
                    self.env.main_program.global_block().vars[name]
                    for name in metrics_name
                ]

            outputs_name = [var.name for var in self.env.outputs]
            self.env.outputs = [
                self.env.main_program.global_block().vars[name]
                for name in outputs_name
            ]

        if self.config.enable_memory_optim:
            for var_name in self.fetch_list:
                var = self.env.main_program.global_block().vars[var_name]
                var.persistable = True

        if self.is_train_phase:
            with fluid.program_guard(self.env.main_program,
                                     self._base_startup_program):
                with fluid.unique_name.guard(self.env.UNG):
                    self.config.strategy.execute(
                        self.loss, self._base_data_reader, self.config)

        if self.is_train_phase:
            loss_name = self.env.loss.name
            share_vars_from = None
        else:
            loss_name = None

        if self._base_compiled_program is None:
            share_vars_from = None
        else:
            share_vars_from = self._base_compiled_program

        if not self.config.use_data_parallel:
            if self.config.enable_memory_optim:
                fluid.memory_optimize(self.env.main_program)
            self.env.main_program_compiled = None
        else:
            self.env.main_program_compiled = fluid.CompiledProgram(
                self.env.main_program).with_data_parallel(
                    loss_name=loss_name,
                    share_vars_from=share_vars_from,
                    build_strategy=self.build_strategy)

            if self._base_compiled_program is None:
                self._base_compiled_program = self.env.main_program_compiled

        self.exe.run(self.env.startup_program)
        self._build_env_end_event()

    @property
    def places(self):
        if self.config.use_cuda:
            _places = fluid.framework.cuda_places()
        else:
            _places = fluid.framework.cpu_places()

        if not self.config.use_data_parallel:
            return [_places[0]]
        return _places

    @property
    def is_train_phase(self):
        return self.phase in ["train"]

    @property
    def is_test_phase(self):
        return self.phase in ["val", "dev", "test"]

    @property
    def is_predict_phase(self):
        return self.phase in ["predict", "inference"]

    @property
    def phase(self):
        return self._phases[-1]

    @property
    def env(self):
        phase = self.phase
        if phase in ["val", "dev", "test"]:
            phase = "val"
        if not phase in self._envs:
            self._envs[phase] = RunEnv()
        return self._envs[phase]

    @property
    def py_reader(self):
        if not self.env.is_inititalized:
            self._build_env()
        return self.env.py_reader

    @property
    def current_step(self):
        if not self.env.is_inititalized:
            self._build_env()
        return self.env.current_step

    @property
    def current_epoch(self):
        if not self.env.is_inititalized:
            self._build_env()
        return self.env.current_epoch

    @property
    def main_program(self):
        if not self.env.is_inititalized:
            self._build_env()
        return self.env.main_program

    @property
    def startup_program(self):
        if not self.env.is_inititalized:
            self._build_env()
        return self.env.startup_program

    @property
    def main_program_compiled(self):
        if not self.env.is_inititalized:
            self._build_env()
        return self.env.main_program_compiled

    @property
    def main_program_to_be_run(self):
        if self.config.use_data_parallel:
            return self.main_program_compiled
        return self.main_program

    @property
    def reader(self):
        if self.is_predict_phase:
            data = self._predict_data
        else:
            data = None
        self.env.reader = self._base_data_reader.data_generator(
            batch_size=self.config.batch_size, phase=self.phase, data=data)
        return self.env.reader

    @property
    def loss(self):
        if self.is_predict_phase:
            raise RuntimeError()

        if not self.env.is_inititalized:
            self._build_env()
        return self.env.loss

    @property
    def labels(self):
        if self.is_predict_phase:
            raise RuntimeError()

        if not self.env.is_inititalized:
            self._build_env()
        return self.env.labels

    @property
    def outputs(self):
        if not self.env.is_inititalized:
            self._build_env()
        return self.env.outputs

    @property
    def metrics(self):
        if self.is_predict_phase:
            raise RuntimeError()

        if not self.env.is_inititalized:
            self._build_env()
        return self.env.metrics

    @property
    def unique_name_generator(self):
        return self.env.UNG

    @property
    def feed_list(self):
        feed_list = [varname for varname in self._base_feed_list]
        if self.is_train_phase or self.is_test_phase:
            feed_list += [label.name for label in self.labels]
        return feed_list

    @property
    def feed_var_list(self):
        vars = self.main_program.global_block().vars
        return [vars[varname] for varname in self.feed_list]

    @property
    def fetch_list(self):
        if self.is_train_phase or self.is_test_phase:
            return [metric.name for metric in self.metrics] + [self.loss.name]
        return [output.name for output in self.outputs]

    def _build_env_start_event(self):
        pass

    def _build_env_end_event(self):
        pass

    def _finetune_start_event(self):
        self.logger.info("TL-Lib finetune start")

    def _finetune_end_event(self, run_states):
        self.logger.info("TL-Lib finetune finished.")

    def _predict_start_event(self):
        self.logger.info("TL-Lib predict start")

    def _predict_end_event(self, run_states):
        self.logger.info("TL-Lib predict finished.")

    def _eval_start_event(self):
        self.logger.info("Evaluation on {} dataset start".format(self.phase))

    def _eval_end_event(self, run_states):
        run_speed = self._calculate_metrics(run_states)
        self.logger.info("[%s dataset evaluation result] [step/sec: %.2f]" %
                    (self.phase, run_speed))

    def _log_interval_event(self, run_states):
        run_speed = self._calculate_metrics(run_states)
        self.logger.info(
            "step %d: [step/sec: %.2f]" % (self.current_step, run_speed))

    def _save_ckpt_interval_event(self):
        self.save_checkpoint()

    def _eval_interval_event(self):
        self.eval(phase="dev")

    def _run_step_event(self, run_state):
        if self.is_predict_phase:
            yield run_state.run_results

    def _build_net(self):
        raise NotImplementedError

    def _add_loss(self):
        raise NotImplementedError

    def _add_label(self):
        raise NotImplementedError

    def _add_metrics(self):
        raise NotImplementedError

    def _calculate_metrics(self, run_states):
        raise NotImplementedError

    # NOTE: current saved checkpoint machanism is not completed,
    # it can't restore dataset training status
    def save_checkpoint(self):
        save_checkpoint(
            checkpoint_dir=self.config.checkpoint_dir,
            current_epoch=self.current_epoch,
            global_step=self.current_step,
            exe=self.exe,
            main_program=self.main_program)

    def load_checkpoint(self):
        is_load_successful, self.env.current_epoch, self.env.current_step = load_checkpoint(
            self.config.checkpoint_dir,
            self.exe,
            main_program=self.main_program)

        return is_load_successful

    def load_parameters(self, dirname):
        def if_exist(var):
            path = os.path.join(dirname, var.name)
            return os.path.exists(path)

        fluid.io.load_vars(
            self.exe, dirname, self.main_program, predicate=if_exist)

    def save_parameters(self, dirname):
        fluid.io.save_params(
            self.exe, dirname=dirname, main_program=self.main_program)

    def finetune_and_eval(self):
        return self.finetune(do_eval=True)

    def finetune(self, do_eval=False):
        # Start to finetune
        with self.phase_guard(phase="train"):
            self.init_if_necessary()
            self._finetune_start_event()
            run_states = []
            if self.current_epoch <= self.config.num_epoch:
                while self.current_epoch <= self.config.num_epoch:
                    run_states = self._run(do_eval=do_eval)
                    self.env.current_epoch += 1

                # Save checkpoint after finetune
                self.save_checkpoint()

                # Final evaluation
                if self._base_data_reader.get_dev_examples() != []:
                    self.eval(phase="dev")
                if self._base_data_reader.get_test_examples() != []:
                    self.eval(phase="test")

            self._finetune_end_event(run_states)
            return run_states

    def eval(self, phase="dev"):
        with self.phase_guard(phase=phase):
            self.init_if_necessary()
            self._eval_start_event()
            run_states = self._run()
            self._eval_end_event(run_states)
            return run_states

    def predict(self, data, load_best_model=True):
        with self.phase_guard(phase="predict"):
            self.init_if_necessary()
            if load_best_model:
                best_model_path = os.path.join(self.config.checkpoint_dir,
                                               "best_model")
                self.load_parameters(best_model_path)
            self._predict_data = data
            self._predict_start_event()
            run_states = self._run()
            self._predict_end_event(run_states)
            self._predict_data = None
        return run_states

    def _run(self, do_eval=False):
        with fluid.program_guard(self.main_program, self.startup_program):
            if self.config.use_pyreader:
                return self._run_with_py_reader(do_eval=do_eval)
            return self._run_with_data_feeder(do_eval=do_eval)

    def _run_with_data_feeder(self, do_eval=False):

        data_feeder = fluid.DataFeeder(
            feed_list=self.feed_list, place=self.place)

        global_run_states = []
        period_run_states = []

        for run_step, batch in enumerate(self.reader(), start=1):
            if self.config.use_data_parallel and len(batch) < self.device_count:
                continue

            step_run_state = RunState(len(self.fetch_list))
            step_run_state.run_step = 1
            num_batch_examples = len(batch)

            fetch_result = self.exe.run(
                self.main_program_to_be_run,
                feed=data_feeder.feed(batch),
                fetch_list=self.fetch_list)

            for index, result in enumerate(fetch_result):
                step_run_state.run_results[index] = result
            step_run_state.run_examples += num_batch_examples
            step_run_state.update()
            period_run_states += [step_run_state]
            self.env.current_step += 1
            if self.is_train_phase:
                if self.current_step % self.config.log_interval == 0:
                    self._log_interval_event(period_run_states)
                    global_run_states += period_run_states
                    period_run_states = []

                if self.config.save_ckpt_interval and self.current_step % self.config.save_ckpt_interval == 0:
                    self._save_ckpt_interval_event()

                if do_eval and self.current_step % self.config.eval_interval == 0:
                    self._eval_interval_event()

            self._run_step_event(step_run_state)

        global_run_states += period_run_states
        return global_run_states

    def _run_with_py_reader(self, do_eval=False):
        flag = False
        use_data_parallel_backup = self.config.use_data_parallel
        while True:
            global_run_states = []
            period_run_states = []
            self.py_reader.decorate_paddle_reader(self.reader)
            self.py_reader.start()
            try:
                while True:
                    num_batch_examples = self.config.batch_size * self.device_count
                    step_run_state = RunState(len(self.fetch_list))
                    step_run_state.run_step = 1
                    fetch_result = self.exe.run(
                        self.main_program_to_be_run, fetch_list=self.fetch_list)

                    for index, result in enumerate(fetch_result):
                        step_run_state.run_results[index] = result
                    step_run_state.run_examples += num_batch_examples
                    step_run_state.update()
                    period_run_states += [step_run_state]
                    self.env.current_step += 1
                    if self.is_train_phase:
                        if self.current_step % self.config.log_interval == 0:
                            self._log_interval_event(period_run_states)
                            global_run_states += period_run_states
                            period_run_states = []

                        if self.config.save_ckpt_interval and self.current_step % self.config.save_ckpt_interval == 0:
                            self._save_ckpt_interval_event()

                        if do_eval and self.current_step % self.config.eval_interval == 0:
                            self._eval_interval_event()

                    self._run_step_event(step_run_state)
            except fluid.core.EOFException:
                global_run_states += period_run_states
                self.py_reader.reset()
                '''
                When opening use_data_parallel and use_pyreader, if the amount of data is too small,
                the reader will have thrown EOF Exception when not fetching to the running result.
                In this case, temporarily close the use_data_parallel to get the result.
                '''
                if flag:
                    self.config._use_data_parallel = use_data_parallel_backup
                elif len(global_run_states) == 0:
                    flag = True
                    self.config._use_data_parallel = False
                    continue
                break

        return global_run_states


class ClassifierTask(BasicTask):
    def __init__(self,
                 feature,
                 num_classes,
                 feed_list,
                 data_reader,
                 startup_program=None,
                 config=None,
                 hidden_units=None,
                 logger=None):

        main_program = feature.block.program

        super(ClassifierTask, self).__init__(
            data_reader=data_reader,
            main_program=main_program,
            feed_list=feed_list,
            startup_program=startup_program,
            config=config,
            logger=logger)

        self.feature = feature
        self.num_classes = num_classes
        self.hidden_units = hidden_units
        self.best_accuracy = -1
        self.logger = logger

    def _build_net(self):
        cls_feats = self.feature
        if self.hidden_units is not None:
            for n_hidden in self.hidden_units:
                cls_feats = fluid.layers.fc(
                    input=cls_feats, size=n_hidden, act="relu")

        logits = fluid.layers.fc(
            input=cls_feats,
            size=self.num_classes,
            param_attr=fluid.ParamAttr(
                name="cls_out_w",
                initializer=fluid.initializer.TruncatedNormal(scale=0.02)),
            bias_attr=fluid.ParamAttr(
                name="cls_out_b", initializer=fluid.initializer.Constant(0.)),
            act="softmax")

        return [logits]

    def _add_label(self):
        return [fluid.layers.data(name="label", dtype="int64", shape=[1])]

    def _add_loss(self):
        ce_loss = fluid.layers.cross_entropy(
            input=self.outputs[0], label=self.labels[0])
        return fluid.layers.mean(x=ce_loss)

    def _add_metrics(self):
        return [
            fluid.layers.accuracy(input=self.outputs[0], label=self.labels[0])
        ]

    def _build_env_end_event(self):
        with self.log_writer.mode(self.phase) as logw:
            if not self.is_predict_phase:
                self.env.loss_scalar = logw.scalar(
                    tag="Loss [{}]".format(self.phase))
                self.env.acc_scalar = logw.scalar(
                    tag="Accuracy [{}]".format(self.phase))

    def _calculate_metrics(self, run_states):
        loss_sum = acc_sum = run_examples = 0
        run_step = run_time_used = 0
        for run_state in run_states:
            run_examples += run_state.run_examples
            run_step += run_state.run_step
            loss_sum += np.mean(
                run_state.run_results[-1]) * run_state.run_examples
            acc_sum += np.mean(
                run_state.run_results[0]) * run_state.run_examples

        run_time_used = time.time() - run_states[0].run_time_begin
        avg_loss = loss_sum / run_examples
        avg_acc = acc_sum / run_examples
        run_speed = run_step / run_time_used

        return avg_loss, avg_acc, run_speed

    def _log_interval_event(self, run_states):
        avg_loss, avg_acc, run_speed = self._calculate_metrics(run_states)
        self.env.loss_scalar.add_record(self.current_step, avg_loss)
        self.env.acc_scalar.add_record(self.current_step, avg_acc)
        self.logger.info("step %d: loss=%.5f acc=%.5f [step/sec: %.2f]" %
                    (self.current_step, avg_loss, avg_acc, run_speed))

    def _eval_end_event(self, run_states):
        eval_loss, eval_acc, run_speed = self._calculate_metrics(run_states)
        self.logger.info(
            "[%s dataset evaluation result] loss=%.5f acc=%.5f [step/sec: %.2f]"
            % (self.phase, eval_loss, eval_acc, run_speed))
        self.env.loss_scalar.add_record(self.current_step, eval_loss)
        self.env.acc_scalar.add_record(self.current_step, eval_acc)
        if self.phase in ["dev", "val"] and eval_acc > self.best_accuracy:
            self.best_accuracy = eval_acc
            model_saved_dir = os.path.join(self.config.checkpoint_dir,
                                           "best_model")
            self.logger.info("best model saved to %s [best accuracy=%.5f]" %
                        (model_saved_dir, self.best_accuracy))
            save_result = fluid.io.save_persistables(
                executor=self.exe,
                dirname=model_saved_dir,
                main_program=self.main_program)

ImageClassifierTask = ClassifierTask