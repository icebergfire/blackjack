"""Проверки правил стола на известных последовательностях карт."""

from random import Random
from unittest import TestCase

from game import START_BALANCE, Action, Card, Hand, Outcome, Phase, Suit, Table


def scripted(*ranks: int, balance: int = START_BALANCE) -> Table:
    """Подготовить законченную стартовую раздачу с известными картами."""
    table = Table(Random(42))
    table.balance = balance
    table.shoe.cards[-len(ranks) :] = [
        Card(rank, Suit.SPADES) for rank in reversed(ranks)
    ]
    table.add_chip(50)
    table.deal()
    return table


def settle(table: Table) -> None:
    """Последовательно обработать раскрытие и все доборы дилера."""
    while table.phase is Phase.DEALER:
        table.advance_dealer()


class TableTest(TestCase):
    """Проверить расчёт ставок, действия игрока и ход дилера."""

    def test_aces_change_value(self) -> None:
        """Тузы считаются за один, когда одиннадцать вызвало бы перебор."""
        hand = Hand([Card(rank, Suit.HEARTS) for rank in (1, 1, 8)])
        self.assertEqual(hand.totals, (10, 20))
        self.assertEqual(hand.score, 20)
        hand.cards.append(Card(7, Suit.CLUBS))
        self.assertEqual(hand.totals, (17,))
        self.assertEqual(hand.score, 17)

    def test_natural_pays_three_to_two(self) -> None:
        """Блэкджек на 50 фишек приносит 75 чистого выигрыша."""
        table = scripted(1, 10, 13, 8)
        self.assertFalse(table.dealer_revealed)
        settle(table)
        self.assertEqual(table.hands[0].outcome, Outcome.BLACKJACK)
        self.assertEqual((table.balance, table.delta), (1075, 75))

    def test_two_naturals_return_bet(self) -> None:
        """Два блэкджека дают ничью и возврат исходной ставки."""
        table = scripted(1, 1, 13, 12)
        settle(table)
        self.assertEqual(table.hands[0].outcome, Outcome.PUSH)
        self.assertEqual((table.balance, table.pushes), (1000, 1))

    def test_dealer_natural_blocks_player_actions(self) -> None:
        """При блэкджеке дилера ход игроку не передаётся."""
        table = scripted(10, 1, 9, 12)
        self.assertFalse(table.available())
        settle(table)
        self.assertEqual((table.balance, table.losses), (950, 1))

    def test_dealer_stands_on_soft_seventeen(self) -> None:
        """Дилер останавливается на тузе и шестёрке."""
        table = scripted(10, 1, 8, 6, 13)
        table.play(Action.STAND)
        settle(table)
        self.assertEqual(len(table.dealer.cards), 2)
        self.assertEqual(table.balance, 1050)

    def test_double_draws_exactly_one_card(self) -> None:
        """Удвоение увеличивает ставку, берёт карту и заканчивает ход."""
        table = scripted(5, 10, 6, 8, 10)
        table.play(Action.DOUBLE)
        self.assertEqual(table.phase, Phase.DEALER)
        self.assertEqual(len(table.hands[0].cards), 3)
        self.assertEqual(table.hands[0].stake, 100)
        settle(table)
        self.assertEqual(table.balance, 1100)

    def test_split_settles_both_hands(self) -> None:
        """Каждая рука после разделения рассчитывается отдельно."""
        table = scripted(8, 10, 8, 6, 10, 9, 10)
        table.play(Action.SPLIT)
        self.assertEqual([hand.score for hand in table.hands], [18, 17])
        self.assertEqual(table.balance, 900)
        table.play(Action.STAND)
        self.assertEqual(table.active, 1)
        table.play(Action.STAND)
        settle(table)
        self.assertEqual(table.balance, 1100)
        self.assertEqual(table.wins, 1)

    def test_split_aces_auto_stand(self) -> None:
        """После разделения тузы получают по карте без выплаты за блэкджек."""
        table = scripted(1, 10, 1, 7, 13, 9)
        table.play(Action.SPLIT)
        self.assertEqual(table.phase, Phase.DEALER)
        self.assertFalse(any(hand.natural for hand in table.hands))
        settle(table)
        self.assertEqual(table.balance, 1100)

    def test_insufficient_balance_blocks_additional_wagers(self) -> None:
        """Без фишек доступны только добор и остановка."""
        table = scripted(8, 10, 8, 7, balance=50)
        self.assertEqual(table.available(), {Action.HIT, Action.STAND})
        table.play(Action.SPLIT)
        self.assertEqual((table.balance, len(table.hands)), (0, 1))

    def test_bust_is_not_rescued_by_dealer(self) -> None:
        """Рука с перебором проигрывает, дилеру добор не требуется."""
        table = scripted(10, 8, 6, 5, 10)
        table.play(Action.HIT)
        settle(table)
        self.assertEqual(table.hands[0].outcome, Outcome.BUST)
        self.assertEqual(len(table.dealer.cards), 2)

    def test_next_round_keeps_valid_prior_bet(self) -> None:
        """Новый раунд очищает карты и предлагает прежнюю ставку."""
        table = scripted(10, 8, 8, 10)
        table.play(Action.STAND)
        settle(table)
        table.next_round()
        self.assertEqual(table.bet, 50)
        self.assertEqual(table.phase, Phase.BET)
        self.assertFalse(table.hands or table.dealer.cards)
