from typing import Protocol


class PipelineStep[T](Protocol):
    async def run(self, item: T) -> T | None:
        pass


class Pipeline[T]:
    def __init__(self, steps: list[PipelineStep[T]]) -> None:
        self._steps = steps

    async def run(self, item: T) -> None:
        for step in self._steps:
            result = await step.run(item)
            if result is None:
                return
            item = result
