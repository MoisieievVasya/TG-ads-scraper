from aiogram.fsm.state import State, StatesGroup


class ReportState(StatesGroup):
    waiting_for_period = State()
    waiting_for_business = State()


class ReportAllState(StatesGroup):
    waiting_for_period = State()
    waiting_for_business = State()