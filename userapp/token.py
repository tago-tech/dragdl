import jwt
import time

# 创建token
def create_token(user):
    payload = {
        'username':user['username'],
        'iat':int(time.time()),
        'exp':int(time.time())+600
    }
    token = jwt.encode(payload,'secret',algorithm='HS256')
    return token

# 验证token并创建新token
def verify_token(token):
    try:
        payload = jwt.decode(token,'secret',algorithm='HS256')
        # decode 成 payload,并重新生成用pay生成 token
        token = create_token(payload)
        return token
    except:
        return False

# 由token获取用户名
def tokenUserInfo(token):
    try:
        payload = jwt.decode(token,'secret',algorithm='HS256')
        current_user = payload['username']
        return current_user
    except:
        return 'guest'

def userInfoCheck(request):
        """
            网络请求，
                成功 - 返回用户名
                失败 - 返回 "guest"
        """
        username = 'guest'
        try:
            token = request.META.get('HTTP_AUTH')
            token = verify_token(token)
            username = tokenUserInfo(token)
        except:
            print("[userInfoCheck] 解析token错误")
        finally:
            return username

