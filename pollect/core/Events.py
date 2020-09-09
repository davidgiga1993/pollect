class EventHook:
    """
    Provides functionality for registering and firing events
    """

    def __init__(self):
        """
        Creates a new event handler
        """
        self.__handlers = []

    def __iadd__(self, handler):
        self.__handlers.append(handler)
        return self

    def __isub__(self, handler):
        self.__handlers.remove(handler)
        return self

    def fire(self, *args, **keywargs):
        """
        Fires the event

        :param args: arguments for the event
        :param keywargs: keyword arguments
        """
        for handler in self.__handlers:
            handler(*args, **keywargs)

    def clear_object_handlers(self, in_object):
        """
        Removes all handles for a given object
        :param in_object: Object that should be removed
        :return:
        """
        for handler in self.__handlers:
            if handler.im_self == in_object:
                self -= in_object


class EventBus:
    _INSTANCE = None

    @staticmethod
    def instance():
        if EventBus._INSTANCE is None:
            EventBus._INSTANCE = EventBus()
        return EventBus._INSTANCE

    def __init__(self):
        self.sigint = EventHook()
        self.tick_rate_change = EventHook()
