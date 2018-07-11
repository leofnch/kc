import json
import logging as log
from itertools import chain
import time
from collections import Counter
import cryptogr as cg


def indexmany(a, k):
    return [i for i, e in enumerate(a) if e == k]


def rm_dubl_from_outs(outs, outns):
    """
    Remove dublicated addresses from tnx's outs
    :param outs: list, tnx.outs
    :param outns: list, tnx.outns
    :return: clean outs: list, clean outns: list
    """
    newouts = []
    newoutns = []
    c = dict(Counter(outs))
    for o in c:
        if c[o] > 1:
            newouts.append(o)
            outn = 0
            for i in indexmany(outs, o):
                outn += outns[i]
            newoutns.append(outn)
        else:
            newouts.append(o)
            newoutns.append(outns[outs.index(o)])
    return newouts, newoutns


def is_tnx_money_valid(self, bch):
    """
    Validate tnx
    :param self: Transaction
    :param bch: Blockchain
    :return: validness(bool)
    """
    inp = 0
    for o in self.outns:
        if round(o, 10) != o:
            return False
    for t in self.froms:  # how much money are available
        try:
            if not bch[int(t[0])].is_unfilled:
                tnx = bch[int(t[0])].txs[int(t[1])]
            else:
                if bch[int(t[0])].get_tnx(int(t[1])):
                    tnx = bch[int(t[0])].get_tnx(int(t[1]))
                else:
                    tnx = bch.get_block(int(t[0])).txs[int(t[1])]
            clean_outs = rm_dubl_from_outs([bch.pubkey_by_nick(out) for out in tnx.outs], tnx.outns)
            is_first = t[0] == 0 and t[1] == 0
            if not tnx.is_valid and not is_first:
                log.debug(self.index, 'is not valid: from(', tnx.index, ') is not valid')
                return False
            if self.author not in tnx.outs:
                return False
            if tnx.spent(bch, [self.index])[clean_outs[0].index(bch.pubkey_by_nick(self.author))]:
                log.debug(self.index, 'is not valid: from(', tnx.index, ') is not valid as from')
                return False
            inp += clean_outs[1][clean_outs[0].index(bch.pubkey_by_nick(self.author))]
        except Exception as e:
            log.debug(str(self.index) + ' is not valid: exception: ' + str(e))
            return False
    o = 0
    for n in self.outns:  # all money must be spent
        if n < 0:
            return False
        o = o + n
    if not o == inp:
        log.debug(self.index, 'is not valid: not all money')
        return False
    return True


def sign_tnx(self, sign, privkey, t):
    """
    Sign tnx with privkey or use existing sign
    :param self: tnx
    :param sign: existing sign or 'signing'
    :param privkey: private key or nothing
    :param t: existing timestamp if privkey is 'signing' or something else
    :return: sign (str)
    """
    if sign == 'signing':
        self.sign = cg.sign(self.hash, privkey)
    else:
        self.sign = sign
    return self.sign  # TODO: timestamp


class Transaction:
    """Class for transaction.
    To create new transaction, use:
    tnx=Transaction()
    tnx.gen(parameters)"""

    def __init__(self):
        self.froms = None
        self.outs = None
        self.outns = None
        self.author = None
        self.index = None
        self.timestamp = None
        self.sign = None
        self.hash = None

    def __str__(self):
        """Encodes transaction to str using JSON"""
        return json.dumps((self.author, self.froms, self.outs, self.outns, self.index,
                           self.sign, self.timestamp))

    @classmethod
    def from_json(cls, s):
        """Decodes transacion from str using JSON"""
        s = json.loads(s)
        self = cls()
        try:
            self.gen(s[0], s[1], s[2], s[3], list(s[4]), s[5], '', s[6])
        except TypeError:
            self.gen(s[0], s[1], s[2], s[3], list(s[4]), 'mining', '', s[6])
        for i in range(len(self.outns)):
            self.outns[i] = round(self.outns[i], 10)
        self.update()
        return self

    def gen(self, author, froms, outs, outns, index, sign='signing', privkey='', t='now'):
        self.froms = froms  # transactions to get money from
        self.outs = outs  # destinations
        self.outns = outns  # values of money on each destination
        self.author = author
        self.index = list(index)
        self.timestamp = time.time() if t == 'now' else t
        for i in range(len(self.outns)):
            self.outns[i] = round(self.outns[i], 10)
        self.update()
        self.sign = sign_tnx(self, sign, privkey, t)
        self.update()

    def is_valid(self, bch):
        """Returns validness of transaction.
        Checks:
        is sign valid
        are all money spent"""
        # check outs and outns are not empty
        if not (self.outs and self.outns):
            return False
        # check validness of nick definition
        if ';' in self.author:
            if bch.pubkey_by_nick(self.author) != self.author.split(';')[0]:   # todo: control nick emission
                return False
        # check validness of tnx made by smart contract
        if self.author[0:2] == 'sc':
            if not bch[int(self.author.split('[')[1][:-1].split(',')[0])].contracts[int(
                    self.author.split('[')[1][:-1].split(', ')[1])].validate_tnx(self, bch):
                return False
        # check sign
        else:
            try:
                if not cg.verify_sign(self.sign, self.hash, bch.pubkey_by_nick(self.author)):
                    log.debug(str(self.index) + ' is not valid: sign is wrong')
                    return False
            except Exception as e:
                log.debug(str(self.index) + ' is not valid: exception while checking sign: ' + str(e))
        # validate transaction money, for example froms and outs should be equal
        if not is_tnx_money_valid(self, bch):
            return False
        self.update()
        return True

    def __eq__(self, other):
        """Compare with other tnx"""
        return self.hash == other.hash

    def spent(self, bch, exc=tuple()):
        """
        :param bch: Blockchain
        :param exc: txs to exclude
        :return: Is transaction used by other transaction
        """
        outs, outns = rm_dubl_from_outs(self.outs, self.outns)
        spent = [False] * len(outs)
        for block in bch:  # перебираем все транзакции в каждом блоке
            for tnx in block.txs[1:]:
                if tuple(self.index) in [tuple(from_ind) for from_ind in tnx.froms] and tnx.index not in exc and \
                        tnx.author in outs:
                    spent[outs.index(tnx.author)] = True
        return spent

    def update(self):
        """
        Update hash
        """
        x = ''.join(chain(str(self.author), str(self.index), [str(f) for f in self.froms],
                          [str(f) for f in self.outs], [str(f) for f in self.outns], str(self.timestamp)))
        self.hash = cg.h(str(x))
