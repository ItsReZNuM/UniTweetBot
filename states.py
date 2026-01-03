
class S:
    IDLE = "IDLE"

    MAIN_MENU = "MAIN_MENU"   
    TWEET_MODE = "TWEET_MODE"  

    USER_WAIT_MAJOR = "USER_WAIT_MAJOR"
    USER_SHOW_RESULTS = "USER_SHOW_RESULTS"

    ADMIN_MENU = "ADMIN_MENU"
    ADMIN_ADD_WAIT_MAJOR = "ADMIN_ADD_WAIT_MAJOR"
    ADMIN_ADD_WAIT_FILE = "ADMIN_ADD_WAIT_FILE"

    ADMIN_DEL_WAIT_QUERY = "ADMIN_DEL_WAIT_QUERY"
    ADMIN_DEL_SHOW_RESULTS = "ADMIN_DEL_SHOW_RESULTS"
    ADMIN_DEL_CONFIRM = "ADMIN_DEL_CONFIRM"



user_state = {}


def get_state(user_id: int) -> str:
    return user_state.get(user_id, {}).get("state", S.IDLE)


def set_state(user_id: int, state: str, data: dict | None = None):
    if user_id not in user_state:
        user_state[user_id] = {"state": state, "data": {}}
    user_state[user_id]["state"] = state
    if data is not None:
        user_state[user_id]["data"] = data


def get_data(user_id: int) -> dict:
    return user_state.get(user_id, {}).get("data", {})


def update_data(user_id: int, **kwargs):
    if user_id not in user_state:
        user_state[user_id] = {"state": S.IDLE, "data": {}}
    user_state[user_id]["data"].update(kwargs)


def reset(user_id: int):
    user_state[user_id] = {"state": S.IDLE, "data": {}}
