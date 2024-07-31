import json


class Session:
    def __init__(self, sessionId):
        if isinstance(sessionId, str):
            self.sessionId = sessionId
        else:
            raise TypeError("You must use an string object for sessionId")
        
        self.eventCbs = {}
        self.messageCbs = {}
        self.messageId = 0

    def send_command(self, command, params, **kwargs):
        cb = kwargs("cb", None)

        if cb:
            self.messageCbs[self.messageId] = cb

        if not isinstance(command, str):
            raise TypeError("You must use an string for the command parameter")
        json_command = {
            "method": command,
            "params": params,
            "Id": self.messageId,
            "messageCbs": self.messageCbs,
        }
        self.messageId = +1
        return json.dumps(json_command)
