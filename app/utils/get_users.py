import re


def check_username(username):
    """
    校验用户名
    规则：
    - 不能为空
    - 长度 3~15 位
    - 只允许字母、数字、下划线、连字符
    返回：(是否通过, 错误信息)  -> (bool, str|None)
    """
    if not username:
        return False, "用户名不能为空"

    username = username.strip()

    if len(username) < 3:
        return False, "用户名不能少于 3 位"
    if len(username) > 15:
        return False, "用户名不能超过 15 位"

    if not re.match(r"^[a-zA-Z0-9_-]+$", username):
        return False, "用户名只能包含字母、数字、下划线(_)和连字符(-)"

    # 可选：不允许以数字开头（很多系统都这样要求）
    if username[0].isdigit():
        return False, "用户名不能以数字开头"

    return True, None


def check_password(password):
    """
    校验密码
    规则：
    - 不能为空
    - 长度 8~64 位
    - 必须包含大写字母
    - 必须包含小写字母
    - 必须包含数字
    - 可选：必须包含特殊字符
    返回：(是否通过, 错误信息)  -> (bool, str|None)
    """
    if not password:
        return False, "密码不能为空"

    if len(password) < 8:
        return False, "密码不能少于 8 位"
    if len(password) > 64:
        return False, "密码不能超过 64 位"

    # 分别检查是否包含
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    # 如果需要特殊字符，取消注释下面这行
    # has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

    if not has_upper:
        return False, "密码必须包含至少一个大写字母"
    if not has_lower:
        return False, "密码必须包含至少一个小写字母"
    if not has_digit:
        return False, "密码必须包含至少一个数字"
    # if not has_special:
    #     return False, "密码必须包含至少一个特殊字符"

    return True, None