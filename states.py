from aiogram.fsm.state import StatesGroup, State

class Register(StatesGroup):
    full_name = State()

class AdminClean(StatesGroup):
    choose_action = State()
    input_user_number = State()
    confirm_delete_user = State()
    confirm_delete_all = State()

class AdminLimits(StatesGroup):
    menu = State()
    set_att_hours = State()
    set_hw_days = State()