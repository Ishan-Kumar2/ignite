from collections import OrderedDict
from typing import Callable, cast, Mapping, Optional

from ignite.base import Serializable
from ignite.engine import Engine
from ignite.utils import setup_logger

__all__ = ["NoImprovementHandler", "EarlyStopping"]


class NoImprovementHandler(Serializable):
    """NoImprovementHandler is a generalised version of Early stopping where you can define what should
    happen if no improvement occurs after a given number of events.
    Args:
        patience: Number of events to wait if no improvement and then call stop_function.
        score_function: It should be a function taking a single argument, an :class:`~ignite.engine.engine.Engine`
            object, and return a score `float`. An improvement is considered if the score is higher.
        pass_function: It should be a function taking a single argument, the trainer
            object, and defines what to do in the case when the stopping condition is not met.
        stop_function: It should be a function taking a single argument, the trainer
            object, and defines what to do in the case when the stopping condition is met.
        trainer: Trainer engine to stop the run if no improvement.
        min_delta: A minimum increase in the score to qualify as an improvement,
            i.e. an increase of less than or equal to `min_delta`, will count as no improvement.
        cumulative_delta: It True, `min_delta` defines an increase since the last `patience` reset, otherwise,
            it defines an increase after the last event. Default value is False.
    Examples:
        .. code-block:: python

            #Example where if the score doesn't improve a user defined value `alpha` is doubled.

            from ignite.engine import Engine, Events
            from ignite.handlers import NoImprovementHandler
            def score_function(engine):
                val_loss = engine.state.metrics['nll']
                return -val_loss
            def pass_function(engine):
                pass
            def stop_function(trainer):
                trainer.state.alpha *= 2

            trainer = Engine(do_nothing_update_fn)
            trainer.state_dict_user_keys.append("alpha")
            trainer.state.alpha = 0.1

            h = NoImprovementHandler(patience=3, score_function=score_function, pass_function=pass_function,
                                     stop_function=stop_function, trainer=trainer)

            # Note: the handler is attached to an *Evaluator* (runs one epoch on validation dataset).
            evaluator.add_event_handler(Events.COMPLETED, handler)
    """

    def __init__(
        self,
        patience: int,
        score_function: Callable,
        pass_function: Callable,
        stop_function: Callable,
        trainer: Engine,
        min_delta: float = 0.0,
        cumulative_delta: bool = False,
    ):

        if not callable(score_function):
            raise TypeError("Argument score_function should be a function.")

        if not callable(pass_function):
            raise TypeError("Argument pass_function should be a function.")

        if not callable(stop_function):
            raise TypeError("Argument stop_function should be a function.")

        if not isinstance(trainer, Engine):
            raise TypeError("Argument trainer should be an instance of Engine.")

        if patience < 1:
            raise ValueError("Argument patience should be positive integer.")

        if min_delta < 0.0:
            raise ValueError("Argument min_delta should not be a negative number.")

        self.patience = patience
        self.score_function = score_function
        self.pass_function = pass_function
        self.stop_function = stop_function
        self.trainer = trainer
        self.counter = 0
        self.best_score = None  # type: Optional[float]
        self.min_delta = min_delta
        self.cumulative_delta = cumulative_delta

    def __call__(self, engine: Engine) -> None:
        score = self.score_function(engine)

        self._update_state(score)
        if self.counter >= self.patience:
            self.stop_function(self.trainer)
        else:
            self.pass_function(self.trainer)

    def _update_state(self, score: int) -> None:

        if self.best_score is None:
            self.best_score = score

        elif score <= self.best_score + self.min_delta:
            if not self.cumulative_delta and score > self.best_score:
                self.best_score = score
            self.counter += 1

        else:
            self.best_score = score
            self.counter = 0

    def state_dict(self) -> "OrderedDict[str, float]":
        """Method returns state dict with ``counter`` and ``best_score``.
        Can be used to save internal state of the class.
        """
        return OrderedDict([("counter", self.counter), ("best_score", cast(float, self.best_score))])

    def load_state_dict(self, state_dict: Mapping) -> None:
        """Method replace internal state of the class with provided state dict data.

        Args:
            state_dict: a dict with "counter" and "best_score" keys/values.
        """
        super().load_state_dict(state_dict)
        self.counter = state_dict["counter"]
        self.best_score = state_dict["best_score"]


class EarlyStopping(NoImprovementHandler):
    """EarlyStopping handler can be used to stop the training if no improvement after a given number of events.
    Args:
        patience: Number of events to wait if no improvement and then stop the training.
        score_function: It should be a function taking a single argument, an :class:`~ignite.engine.engine.Engine`
            object, and return a score `float`. An improvement is considered if the score is higher.
        trainer: Trainer engine to stop the run if no improvement.
        min_delta: A minimum increase in the score to qualify as an improvement,
            i.e. an increase of less than or equal to `min_delta`, will count as no improvement.
        cumulative_delta: It True, `min_delta` defines an increase since the last `patience` reset, otherwise,
            it defines an increase after the last event. Default value is False.
    Examples:
        .. code-block:: python
            from ignite.engine import Engine, Events
            from ignite.handlers import EarlyStopping
            def score_function(engine):
                val_loss = engine.state.metrics['nll']
                return -val_loss
            handler = EarlyStopping(patience=10, score_function=score_function, trainer=trainer)
            # Note: the handler is attached to an *Evaluator* (runs one epoch on validation dataset).
            evaluator.add_event_handler(Events.COMPLETED, handler)
    """

    _state_dict_all_req_keys = (
        "counter",
        "best_score",
    )

    def __init__(
        self,
        patience: int,
        score_function: Callable,
        trainer: Engine,
        min_delta: float = 0.0,
        cumulative_delta: bool = False,
    ):
        super(EarlyStopping, self).__init__(
            patience=patience,
            score_function=score_function,
            pass_function=self.pass_function,
            stop_function=self.stop_function,
            trainer=trainer,
            min_delta=min_delta,
            cumulative_delta=cumulative_delta,
        )

        self.logger = setup_logger(__name__ + "." + self.__class__.__name__)

    def __call__(self, engine: Engine) -> None:
        super(EarlyStopping, self).__call__(engine)

    def pass_function(self, trainer: Engine) -> None:
        pass

    def stop_function(self, trainer: Engine) -> None:
        self.logger.info("EarlyStopping: Stop training")
        trainer.terminate()
