

def user_info(request):
    user_dict = request.user.as_dict()

    del user_dict['password']

    user_dict["status"] = "success"

    return user_dict
