import datetime


class Job(object):
    itemId: str
    url: str
    result: str | None | bool
    processedBy: str | None

    def __init__(self, data, itemId=None):
        self.itemId = datetime.datetime.now().strftime(
            f'%y%m%d/%H%M%S') if itemId is None else itemId
        self.url = data
        self.result = None
        self.processedBy = None

    def __repr__(self) -> str:
        if self.result is None:
            return f"Uncompleted Job: {self.itemId}"
        else:
            if self.result is False:
                return f'Failed Job: {self.itemId} :: {self.processedBy}'
            else:
                return f"Completed Job: {self.itemId} :: {self.processedBy}"

    @staticmethod
    def from_dict(classname, d):
        """Method used to deserialize a job from Pyro"""
        job = Job(d["data"], d["itemId"])
        job.result = None if d["result"] == 'None' else False if d["result"].lower(
        ) == 'false' else d["result"]
        job.processedBy = d["processedBy"]
        return job
