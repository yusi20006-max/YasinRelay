from yasin_core.core.runtime import YasinRuntime
from yasin_core.events.event_bus import EventBus


def test_runtime():

    runtime = YasinRuntime()

    runtime.start()

    status = runtime.status()

    assert status["running"] is True



def test_event_bus():

    bus = EventBus()

    result = []


    def handler(data):

        result.append(data)


    bus.subscribe(
        "TEST",
        handler
    )


    bus.publish(
        "TEST",
        "hello"
    )


    assert result[0] == "hello"
