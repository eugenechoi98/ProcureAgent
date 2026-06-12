"""Phase 3 异常说明数据、训练和评测支持。"""

__all__ = ["AnomalySample", "AnomalyType", "InputFacts"]


def __getattr__(name: str):
    """按需导入 Pydantic schema，避免环境 guard 入口提前失败。"""

    if name in __all__:
        from procureguard.phase3.schemas import AnomalySample, AnomalyType, InputFacts

        values = {
            "AnomalySample": AnomalySample,
            "AnomalyType": AnomalyType,
            "InputFacts": InputFacts,
        }
        return values[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
