import json
from collections import Counter
from block.sc.executors.js.jstask import js
from block.constants import MAXMINERS
import cryptogr as cg


class TaskMiner:
    def __init__(self, difficulty=None, result_hash=None, address=None):
        self.difficulty = difficulty
        self.result_hash = result_hash
        self.address = address

    def __str__(self):
        return json.dumps((self.address, self.difficulty, self.result_hash))

    def run(self, task):
        """
        Run task
        :param task: task to run
        """
        t = task
        t.run()
        self.difficulty = t.difficulty
        self.result_hash = t.result_hash()
        return t.result_dump()

    @classmethod
    def from_json(cls, s):
        return cls(*json.loads(s))


class Task:
    def __init__(self, parents, n, task_class, miners=tuple(), task_data=None):
        """
        init
        :param parents: sc-parent index
        :type parents: list
        :param n: number of this task in sc
        :type n: int
        :param task_class: executor type (str, 'js' or 'wasm')
        :type task_class: str
        :param miners
        :type miners: list
        :param task_data: task data
        :type task_data: str
        """
        self.parent = parents
        self.n = n
        self.miners = list(miners)
        self.task_class = task_class
        self.done = False
        if task_data:
            if task_class == 'js':
                self.task = js[0].from_json(task_data)
        else:
            self.task = None

    def awards(self):
        results = dict(Counter([miner.result_hash for miner in self.miners]))
        results, numbers = results.keys(), results.values()
        number = max(numbers)
        if list(numbers).count(number) > 1:
            return {}
        result = list(results)[list(numbers).index(number)]
        awards = {}
        for miner in self.miners:
            if miner.result_hash == result:
                awards[miner.address] = miner.difficulty
        self.done = True
        return awards

    def find_miner(self, miner):
        for m in self.miners:
            if m.address == miner:
                return m

    def set_miner(self, address, miner):
        for i, m in enumerate(self.miners):
            if m.address == address:
                self.miners[i] = miner
                return

    def task_application(self, miner):
        if len(self.miners) > MAXMINERS:
            return False
        self.miners.append(miner)
        return True

    def is_open(self):
        return len(self.miners) <= MAXMINERS and not self.done

    def __hash__(self):
        return cg.h(json.loads((self.parent, self.n)))

    def __str__(self):
        """
        Convert task to JSON
        :return: task's JSON representation
        :rtype: str
        """
        return json.dumps((self.parent, self.n, [str(miner) for miner in self.miners], self.task_class, str(self.task)))

    @classmethod
    def from_json(cls, s):
        """
        Restore task from JSON
        :param s: task's JSON representation (from Task.__str__)
        :type s: str
        :return: task
        :rtype: Task
        """
        s = json.loads(s)
        miners = [TaskMiner.from_json(st) for st in s[2]]
        return cls(s[0], s[1], s[3], miners, s[4])
