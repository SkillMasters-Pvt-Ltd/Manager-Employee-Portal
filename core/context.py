from .access import get_profile, is_manager_user


def nav(request):
    return {"me": get_profile(request.user), "is_mgr": is_manager_user(request.user)}
