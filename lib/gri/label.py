import logging
import re

LOG = logging.getLogger(__package__)


# pylint: disable=too-few-public-methods
class Label:
    def __init__(self, name, data) -> None:
        self.name = name
        self.abbr = re.sub("[^A-Z]", "", name)
        self.value = 0

        if data.get("blocking", False):
            self.value += -2
        if data.get("approved", False):
            self.value += 2
        if data.get("recommended", False):
            self.value += 1
        if data.get("disliked", False):
            self.value += -1
        if data.get("rejected", False):
            self.value += -1
        if data.get("optional", False):
            self.value = 1
        for unknown in set(data.keys()) - set(
            [
                "blocking",
                "approved",
                "recommended",
                "disliked",
                "rejected",
                "value",
                "optional",
            ]
        ):
            LOG.debug("Found unknown label field %s: %s", unknown, data.get(unknown))

    def is_meta(self) -> bool:
        if self.name in ["Code-Review", "Workflow", "Verified"]:
            return True
        return False

    def __repr__(self) -> str:
        msg = self.abbr + ":" + str(self.value)
        if self.value < 0:
            color = "red"
        elif self.value == 0:
            color = "yellow"
        elif self.value > 0:
            color = "green"
        return f"[{color}]{msg}[/]"
