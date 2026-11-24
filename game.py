"""Карты, ставки и правила настольного блэкджека."""

from dataclasses import dataclass, field
from enum import Enum, auto
from random import Random

# Фишки чётного номинала позволяют выплатить 3:2 целыми числами.
START_BALANCE = 1000
CHIPS = (10, 20, 50, 100)
DECKS = 6
RESHUFFLE_AT = 60
DEALER_STANDS_AT = 17


class Suit(Enum):
    """Четыре масти стандартной колоды."""

    SPADES = auto()
    HEARTS = auto()
    DIAMONDS = auto()
    CLUBS = auto()


@dataclass(frozen=True)
class Card:
    """Карта с рангом от туза (1) до короля (13)."""

    rank: int
    suit: Suit


class Phase(Enum):
    """Состояния, определяющие доступные действия за столом."""

    BET = auto()
    PLAYER = auto()
    DEALER = auto()
    RESULT = auto()


class Action(Enum):
    """Действия игрока после стартовой раздачи."""

    HIT = auto()
    STAND = auto()
    DOUBLE = auto()
    SPLIT = auto()


class Outcome(Enum):
    """Варианты расчёта ставки по одной руке."""

    BLACKJACK = auto()
    WIN = auto()
    PUSH = auto()
    LOSE = auto()
    BUST = auto()


@dataclass
class Hand:
    """Карты одной руки, поставленные фишки и результат."""

    cards: list[Card] = field(default_factory=list)
    stake: int = 0
    split: bool = False
    done: bool = False
    outcome: Outcome | None = None

    @property
    def score(self) -> int:
        """Выбрать наибольшую допустимую сумму с тузом за один или 11."""
        low = sum(min(card.rank, 10) for card in self.cards)
        if low <= 11 and any(card.rank == 1 for card in self.cards):
            return low + 10
        return low

    @property
    def natural(self) -> bool:
        """Определить блэкджек из первых двух карт до разделения."""
        return not self.split and len(self.cards) == 2 and self.score == 21


class Shoe:
    """Перемешанные колоды, общие для последовательных раундов."""

    def __init__(self, random: Random) -> None:
        """Собрать шесть стандартных колод и перемешать карты."""
        self.random = random
        self.cards: list[Card] = []
        self.refresh()

    def refresh(self) -> None:
        """Заново перемешать колоды, когда в башмаке мало карт."""
        self.cards = [
            Card(rank, suit)
            for _ in range(DECKS)
            for suit in Suit
            for rank in range(1, 14)
        ]
        self.random.shuffle(self.cards)

    def draw(self) -> Card:
        """Взять верхнюю карту из башмака."""
        return self.cards.pop()


class Table:
    """Разыгрывать раунды и учитывать баланс фишек игрока."""

    def __init__(self, random: Random | None = None) -> None:
        """Открыть стол со стартовым балансом и пустой ставкой."""
        self.shoe = Shoe(random or Random())
        self.balance = START_BALANCE
        self.bet = 0
        self.last_bet = 0
        self.rounds = 0
        self.wins = 0
        self.pushes = 0
        self.losses = 0
        self.delta = 0
        self.phase = Phase.BET
        self.dealer = Hand()
        self.hands: list[Hand] = []
        self.active = 0
        self.dealer_revealed = False

    def add_chip(self, amount: int) -> None:
        """Увеличить ставку на одну доступную фишку."""
        if (
            self.phase is Phase.BET
            and amount in CHIPS
            and self.bet + amount <= self.balance
        ):
            self.bet += amount

    def clear_bet(self) -> None:
        """Очистить ставку перед раздачей."""
        if self.phase is Phase.BET:
            self.bet = 0

    def deal(self) -> None:
        """Списать ставку и по очереди сдать игроку и дилеру две карты."""
        if self.phase is not Phase.BET or not 0 < self.bet <= self.balance:
            return
        if len(self.shoe.cards) < RESHUFFLE_AT:
            self.shoe.refresh()
        self.balance -= self.bet
        self.last_bet = self.bet
        player = Hand(stake=self.bet)
        self.hands = [player]
        for _ in range(2):
            player.cards.append(self.shoe.draw())
            self.dealer.cards.append(self.shoe.draw())
        if player.natural or self.dealer.natural:
            self.phase = Phase.DEALER
        else:
            self.phase = Phase.PLAYER

    def available(self) -> set[Action]:
        """Вернуть допустимые действия с учётом карт и остатка фишек."""
        if self.phase is not Phase.PLAYER:
            return set()
        hand = self.hands[self.active]
        actions = {Action.HIT, Action.STAND}
        if len(hand.cards) == 2 and self.balance >= hand.stake:
            actions.add(Action.DOUBLE)
            if (
                len(self.hands) == 1
                and hand.cards[0].rank == hand.cards[1].rank
            ):
                actions.add(Action.SPLIT)
        return actions

    def play(self, action: Action) -> None:
        """Разыграть карту, остановиться, удвоить или разделить пару."""
        if action not in self.available():
            return
        hand = self.hands[self.active]
        if action is Action.SPLIT:
            self._split(hand)
        elif action is Action.STAND:
            hand.done = True
        else:
            if action is Action.DOUBLE:
                self.balance -= hand.stake
                hand.stake *= 2
            hand.cards.append(self.shoe.draw())
            hand.done = hand.score >= 21 or action is Action.DOUBLE
        self._advance_hand()

    def advance_dealer(self) -> None:
        """Открыть карту дилера, взять следующую или рассчитать ставки."""
        if self.phase is not Phase.DEALER:
            return
        if not self.dealer_revealed:
            self.dealer_revealed = True
            return
        dealer_needed = not self.dealer.natural and any(
            hand.score <= 21 and not hand.natural for hand in self.hands
        )
        if dealer_needed and self.dealer.score < DEALER_STANDS_AT:
            self.dealer.cards.append(self.shoe.draw())
        else:
            self._settle()

    def next_round(self) -> None:
        """Вернуться к ставкам и предложить ту же сумму, если хватает фишек."""
        if self.phase is not Phase.RESULT:
            return
        self.phase = Phase.BET
        self.bet = self.last_bet if self.last_bet <= self.balance else 0
        self.dealer = Hand()
        self.hands = []
        self.active = 0
        self.dealer_revealed = False

    def _split(self, first: Hand) -> None:
        """Создать вторую руку с той же ставкой и раздать обеим по карте."""
        self.balance -= first.stake
        second = Hand([first.cards.pop()], first.stake, split=True)
        first.split = True
        self.hands.append(second)
        aces = first.cards[0].rank == 1
        for hand in self.hands:
            hand.cards.append(self.shoe.draw())
            hand.done = aces or hand.score >= 21

    def _advance_hand(self) -> None:
        """Перейти к следующей руке или передать ход дилеру."""
        while self.active < len(self.hands) and self.hands[self.active].done:
            self.active += 1
        if self.active == len(self.hands):
            self.phase = Phase.DEALER

    def _settle(self) -> None:
        """Рассчитать каждую руку, вернуть выплаты и обновить статистику."""
        self.delta = 0
        for hand in self.hands:
            outcome, payout = self._payout(hand)
            hand.outcome = outcome
            self.balance += payout
            self.delta += payout - hand.stake
        self.rounds += 1
        self.wins += self.delta > 0
        self.pushes += self.delta == 0
        self.losses += self.delta < 0
        self.phase = Phase.RESULT

    def _payout(self, hand: Hand) -> tuple[Outcome, int]:
        """Вернуть исход руки и сумму, которую получает игрок со ставкой."""
        stake = hand.stake
        if hand.score > 21:
            return Outcome.BUST, 0
        if self.dealer.natural:
            return (Outcome.PUSH, stake) if hand.natural else (Outcome.LOSE, 0)
        if hand.natural:
            return Outcome.BLACKJACK, stake * 5 // 2
        if self.dealer.score > 21 or hand.score > self.dealer.score:
            return Outcome.WIN, stake * 2
        if hand.score == self.dealer.score:
            return Outcome.PUSH, stake
        return Outcome.LOSE, 0
