"""Отрисовка карточного стола, фишек и анимации раздачи."""

from dataclasses import dataclass
from pathlib import Path

import pygame

from game import CHIPS, Action, Card, Hand, Outcome, Phase, Suit, Table

# Базовые координаты масштабируются вместе с окном.
WIDTH, HEIGHT = 1160, 740
TABLE = pygame.Rect(24, 97, 812, 526)
PANEL = pygame.Rect(852, 97, 284, 526)
FOOTER = pygame.Rect(24, 644, 1112, 72)
CARD_SIZE = (76, 106)
DECK_POS = (730, 147)
DEAL_TIME = 0.29
DEAL_GAP = 0.095
FLIP_TIME = 0.36

BACKGROUND = (12, 23, 20)
SURFACE = (21, 37, 30)
EDGE = (63, 83, 71)
GOLD = (228, 193, 127)
GOLD_DARK = (118, 103, 62)
WHITE = (246, 241, 227)
MUTED = (171, 192, 177)
GREEN = (156, 229, 174)
RED = (255, 167, 153)
INK = (26, 39, 33)
CARD_RED = (163, 39, 50)
CHIP_COLORS = dict(
    zip(CHIPS, ((54, 120, 100), (60, 95, 151), (152, 65, 75), (132, 96, 45)))
)
CARD_LABELS = {1: "Т", 11: "В", 12: "Д", 13: "К"}
OUTCOME_LABELS = {
    Outcome.BLACKJACK: ("Блэкджек", GREEN),
    Outcome.WIN: ("Победа", GREEN),
    Outcome.PUSH: ("Ничья", GOLD),
    Outcome.LOSE: ("Проигрыш", RED),
    Outcome.BUST: ("Перебор", RED),
}

Intent = Action | str | int


@dataclass(frozen=True)
class Button:
    """Область управления, одинаковая для отрисовки и клика."""

    rect: pygame.Rect
    label: str
    intent: Intent
    enabled: bool = True
    primary: bool = False


@dataclass
class Motion:
    """Перемещение карты от источника к конечному месту."""

    origin: pygame.Vector2
    target: tuple[int, int]
    starts: float

    def at(self, now: float) -> pygame.Vector2:
        """Вернуть координату карты с плавной остановкой в конце."""
        time = max(0.0, min(1.0, (now - self.starts) / DEAL_TIME))
        return self.origin.lerp(self.target, 1 - (1 - time) ** 3)


def viewport(size: tuple[int, int]) -> pygame.Rect:
    """Вписать игровой стол в окно с сохранением пропорций."""
    width, height = size
    scale = min(width / WIDTH, height / HEIGHT)
    box = pygame.Rect(
        0, 0, max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale))
    )
    box.center = width // 2, height // 2
    return box


def _score_text(hand: Hand) -> str:
    """Подписать обе суммы, пока туз можно считать за один или за 11."""
    return " / ".join(str(total) for total in hand.totals)


def _suit(
    surface: pygame.Surface,
    suit: Suit,
    center: tuple[int, int],
    size: int,
    color: tuple[int, int, int],
) -> None:
    """Нарисовать знак масти без зависимости от символов шрифта."""
    x, y = center
    unit = size / 10

    def points(coords: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Перевести координаты знака в пиксели поверхности."""
        return [
            (round(x + dx * unit), round(y + dy * unit)) for dx, dy in coords
        ]

    radius = max(1, round(2.6 * unit))
    if suit is Suit.DIAMONDS:
        pygame.draw.polygon(
            surface, color, points([(0, -5), (4, 0), (0, 5), (-4, 0)])
        )
    elif suit is Suit.CLUBS:
        for point in points([(0, -2), (-2, 1), (2, 1)]):
            pygame.draw.circle(surface, color, point, radius)
        pygame.draw.polygon(surface, color, points([(-2, 5), (0, 1), (2, 5)]))
    else:
        sign = 1 if suit is Suit.HEARTS else -1
        for point in points([(-2, -sign), (2, -sign)]):
            pygame.draw.circle(surface, color, point, radius)
        pygame.draw.polygon(
            surface, color, points([(-4, 0), (4, 0), (0, 5 * sign)])
        )
        if suit is Suit.SPADES:
            pygame.draw.polygon(
                surface, color, points([(-2, 5), (0, 1), (2, 5)])
            )


def _card_back() -> pygame.Surface:
    """Подготовить рубашку с геометрическим орнаментом."""
    surface = pygame.Surface(CARD_SIZE, pygame.SRCALPHA)
    frame = surface.get_rect()
    pygame.draw.rect(surface, WHITE, frame, border_radius=7)
    inner = frame.inflate(-8, -8)
    pygame.draw.rect(surface, (27, 66, 53), inner, border_radius=4)
    pygame.draw.rect(surface, GOLD_DARK, inner.inflate(-6, -6), 1, 3)
    for y in range(15, 100, 10):
        for x in range(14 if y % 20 == 15 else 19, 66, 10):
            _suit(surface, Suit.DIAMONDS, (x, y), 5, (52, 94, 72))
    pygame.draw.circle(surface, (20, 49, 41), frame.center, 21)
    pygame.draw.circle(surface, GOLD, frame.center, 21, 1)
    _suit(surface, Suit.SPADES, frame.center, 23, GOLD)
    return surface


def _card_face(card: Card, font: pygame.font.Font) -> pygame.Surface:
    """Нарисовать лицевую сторону карты с русским обозначением ранга."""
    surface = pygame.Surface(CARD_SIZE, pygame.SRCALPHA)
    frame = surface.get_rect()
    pygame.draw.rect(surface, WHITE, frame, border_radius=7)
    pygame.draw.rect(surface, (222, 210, 181), frame, 1, 7)
    color = CARD_RED if card.suit in (Suit.HEARTS, Suit.DIAMONDS) else INK
    corner = pygame.Surface((25, 36), pygame.SRCALPHA)
    rank = font.render(CARD_LABELS.get(card.rank, str(card.rank)), True, color)
    corner.blit(rank, rank.get_rect(midtop=(12, 0)))
    _suit(corner, card.suit, (12, 25), 11, color)
    surface.blit(corner, (2, 4))
    surface.blit(pygame.transform.rotate(corner, 180), (49, 66))
    if card.rank in CARD_LABELS:
        pygame.draw.circle(surface, (227, 216, 188), frame.center, 19, 1)
    _suit(surface, card.suit, frame.center, 29, color)
    return surface


class TableView:
    """Рисовать состояние стола и интерполировать движение карт."""

    def __init__(self) -> None:
        """Подготовить полотно, материалы и шрифты интерфейса."""
        self.frame = pygame.Surface((WIDTH, HEIGHT)).convert()
        source = Path(__file__).parent / "assets" / "felt.jpg"
        self.felt = pygame.image.load(source).convert_alpha()
        mask = pygame.Surface(TABLE.size, pygame.SRCALPHA)
        pygame.draw.rect(
            mask, (225, 225, 225, 255), mask.get_rect(), border_radius=22
        )
        self.felt.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.back = _card_back()
        self.faces: dict[Card, pygame.Surface] = {}
        self.fonts: dict[tuple[int, bool, bool], pygame.font.Font] = {}
        self.motions: dict[int, Motion] = {}
        self.ready_at = 0.0
        self.flip_at: float | None = None
        self.revealed = False

    def busy(self, now: float) -> bool:
        """Сообщить, продолжается ли раздача или переворот карты."""
        return now < self.ready_at

    def sync(self, table: Table, now: float) -> None:
        """Согласовать размещение и анимацию с новым состоянием стола."""
        cards = self._layout(table)
        if not cards:
            self.motions.clear()
            self.revealed = False
            self.flip_at = None
            self.ready_at = now
            return

        fresh = [id(card) for card, _ in cards if id(card) not in self.motions]
        if not self.motions and len(cards) == 4:
            # Раздаём по кругу: игрок, дилер, игрок, дилер.
            first, second = table.hands[0].cards
            opened, hidden = table.dealer.cards
            fresh = [id(card) for card in (first, opened, second, hidden)]
        delays = {
            card_id: index * DEAL_GAP for index, card_id in enumerate(fresh)
        }
        for card, target in cards:
            card_id = id(card)
            saved = self.motions.get(card_id)
            if saved is not None and saved.target == target:
                continue
            old_pos = saved.at(now) if saved else pygame.Vector2(DECK_POS)
            start = now + delays.get(card_id, 0.0)
            self.motions[card_id] = Motion(old_pos, target, start)
            self.ready_at = max(self.ready_at, start + DEAL_TIME)

        if table.dealer_revealed and not self.revealed:
            self.flip_at = now
            self.ready_at = max(self.ready_at, now + FLIP_TIME)
        self.revealed = table.dealer_revealed

    def buttons(self, table: Table, now: float, rules: bool) -> list[Button]:
        """Собрать кнопки для текущей фазы раунда или окна правил."""
        if rules:
            return [
                Button(
                    pygame.Rect(700, 536, 156, 43),
                    "Понятно",
                    "close",
                    primary=True,
                )
            ]
        buttons = [Button(pygame.Rect(1009, 27, 127, 44), "Правила", "rules")]
        ready = not self.busy(now)
        if table.phase is Phase.BET and table.balance >= CHIPS[0]:
            buttons.extend(
                Button(
                    pygame.Rect(178 + i * 72, 651, 58, 58),
                    str(chip),
                    chip,
                    table.bet + chip <= table.balance,
                )
                for i, chip in enumerate(CHIPS)
            )
            buttons.append(
                Button(
                    pygame.Rect(565, 655, 146, 50),
                    "Сбросить",
                    "clear",
                    table.bet > 0,
                )
            )
            buttons.append(
                Button(
                    pygame.Rect(934, 655, 188, 50),
                    "Раздать",
                    "deal",
                    table.bet > 0,
                    True,
                )
            )
        elif table.phase is Phase.PLAYER:
            available = table.available()
            labels = (
                (Action.HIT, "Взять карту"),
                (Action.STAND, "Остановиться"),
                (Action.DOUBLE, "Удвоить"),
                (Action.SPLIT, "Разделить"),
            )
            buttons.extend(
                Button(
                    pygame.Rect(170 + i * 233, 655, 214, 50),
                    label,
                    action,
                    ready and action in available,
                    action is Action.HIT,
                )
                for i, (action, label) in enumerate(labels)
            )
        elif table.phase is Phase.RESULT:
            buttons.append(
                Button(
                    pygame.Rect(909, 655, 213, 50),
                    "Следующая раздача",
                    "next",
                    ready,
                    True,
                )
            )
        elif table.phase is Phase.BET:
            buttons.append(
                Button(
                    pygame.Rect(920, 655, 202, 50),
                    "Новая сессия",
                    "reset",
                    primary=True,
                )
            )
        return buttons

    def render(
        self,
        table: Table,
        now: float,
        pointer: tuple[float, float],
        rules: bool,
    ) -> pygame.Surface:
        """Собрать полный кадр для отображения в масштабируемом окне."""
        self.frame.fill(BACKGROUND)
        _suit(self.frame, Suit.SPADES, (47, 49), 34, GOLD)
        self._text("Блэкджек", (79, 19), 48, WHITE, serif=True)
        self._text("Баланс", (770, 23), 16, MUTED)
        self._text(
            f"{table.balance:,}".replace(",", " "),
            (770, 45),
            27,
            GOLD,
            bold=True,
        )
        self._table(table, now)
        self._panel(table)
        self._footer(table)
        if rules:
            self._rules()
        for button in self.buttons(table, now, rules):
            self._button(button, button.rect.collidepoint(pointer))
        return self.frame

    def _font(
        self, size: int, bold: bool = False, serif: bool = False
    ) -> pygame.font.Font:
        """Закэшировать шрифт заданного размера и начертания."""
        key = size, bold, serif
        if key not in self.fonts:
            names = "georgia,deja vu serif" if serif else "arial,deja vu sans"
            self.fonts[key] = pygame.font.SysFont(names, size, bold=bold)
        return self.fonts[key]

    def _text(
        self,
        value: str,
        at: tuple[int, int],
        size: int,
        color: tuple[int, int, int],
        *,
        center: bool = False,
        bold: bool = False,
        serif: bool = False,
    ) -> None:
        """Вывести текст с привязкой к углу или центру."""
        text = self._font(size, bold, serif).render(value, True, color)
        self.frame.blit(text, text.get_rect(center=at) if center else at)

    def _groups(self, count: int) -> tuple[int, ...]:
        """Вернуть центры для одной руки или для пары после разделения."""
        if count < 2:
            return (TABLE.centerx,)
        return TABLE.centerx - 194, TABLE.centerx + 194

    def _layout(self, table: Table) -> list[tuple[Card, tuple[int, int]]]:
        """Расположить карты дилера и игрока, сжимая длинные руки."""
        groups = [(table.dealer, TABLE.centerx, 163)]
        groups.extend(
            (hand, x, 442)
            for hand, x in zip(table.hands, self._groups(len(table.hands)))
        )
        result = []
        for hand, x, y in groups:
            spacing = min(57, 239 // max(1, len(hand.cards) - 1))
            start = x - (CARD_SIZE[0] + spacing * (len(hand.cards) - 1)) // 2
            result.extend(
                (card, (start + i * spacing, y))
                for i, card in enumerate(hand.cards)
            )
        return result

    def _table(self, table: Table, now: float) -> None:
        """Нарисовать сукно, колоду и позиции дилера и игрока."""
        self.frame.blit(self.felt, TABLE)
        pygame.draw.rect(self.frame, GOLD_DARK, TABLE, 1, 22)
        pygame.draw.rect(
            self.frame, (69, 128, 98), TABLE.inflate(-18, -18), 1, 16
        )
        self._deck()

        opened = table.dealer_revealed and (
            self.flip_at is None or now >= self.flip_at + FLIP_TIME / 2
        )
        visible = table.dealer if opened else Hand(table.dealer.cards[:1])
        dealer = f"Дилер · {_score_text(visible)}" if visible.cards else "Дилер"
        self._text(
            dealer, (TABLE.centerx, 130), 19, WHITE, center=True, bold=True
        )
        if not table.dealer.cards:
            self._slots(TABLE.centerx, 163)
        if not table.hands:
            self._text(
                "Игрок",
                (TABLE.centerx, 413),
                19,
                WHITE,
                center=True,
                bold=True,
            )
            self._slots(TABLE.centerx, 442)
        for i, (hand, x) in enumerate(
            zip(table.hands, self._groups(len(table.hands)))
        ):
            self._hand_label(table, hand, x, i)

        self._message(table)
        hidden_id = id(table.dealer.cards[1]) if table.dealer.cards else 0
        for card, _ in self._layout(table):
            self._draw_card(card, now, id(card) == hidden_id)

    def _deck(self) -> None:
        """Показать источник карт и край сложенных рубашек."""
        x, y = DECK_POS
        for dx, dy in ((7, 8), (4, 5), (0, 0)):
            self.frame.blit(self.back, (x + dx, y + dy))
        self._text(
            "Колода", (x + CARD_SIZE[0] // 2, y + 129), 15, WHITE, center=True
        )

    def _slots(self, center: int, top: int) -> None:
        """Обозначить свободные места до начала раздачи."""
        for offset in (-82, 6):
            slot = pygame.Rect(center + offset, top, *CARD_SIZE)
            pygame.draw.rect(self.frame, (29, 79, 57), slot, border_radius=8)
            pygame.draw.rect(self.frame, (90, 139, 107), slot, 1, 8)
            _suit(self.frame, Suit.DIAMONDS, slot.center, 20, (81, 129, 99))

    def _hand_label(
        self, table: Table, hand: Hand, x: int, index: int
    ) -> None:
        """Подписать очки и выделить руку, которой сейчас играют."""
        title = f"Рука {index + 1}" if len(table.hands) == 2 else "Игрок"
        active = table.phase is Phase.PLAYER and table.active == index
        if active:
            badge = pygame.Rect(x - 95, 397, 190, 32)
            pygame.draw.rect(self.frame, (20, 69, 49), badge, border_radius=16)
            pygame.draw.rect(self.frame, GOLD_DARK, badge, 1, 16)
        self._text(
            f"{title} · {_score_text(hand)}",
            (x, 413),
            19,
            GOLD if active else WHITE,
            center=True,
            bold=True,
        )
        if hand.outcome is not None:
            label, color = OUTCOME_LABELS[hand.outcome]
            self._text(
                f"{label} · {hand.stake}", (x, 576), 18, color, center=True
            )
        elif len(table.hands) == 2:
            self._text(
                f"Ставка {hand.stake}", (x, 576), 17, MUTED, center=True
            )

    def _draw_card(self, card: Card, now: float, is_hole: bool) -> None:
        """Нарисовать движущуюся карту и перевернуть закрытую в ход дилера."""
        motion = self.motions[id(card)]
        if now < motion.starts:
            return
        x, y = motion.at(now)
        hidden = is_hole and not self.revealed
        width = CARD_SIZE[0]
        if (
            is_hole
            and self.flip_at is not None
            and now < self.flip_at + FLIP_TIME
        ):
            fraction = (now - self.flip_at) / FLIP_TIME
            hidden = fraction < 0.5
            width = max(2, round(CARD_SIZE[0] * abs(2 * fraction - 1)))
        if hidden:
            image = self.back
        else:
            if card not in self.faces:
                self.faces[card] = _card_face(card, self._font(17, bold=True))
            image = self.faces[card]
        if width != CARD_SIZE[0]:
            image = pygame.transform.smoothscale(image, (width, CARD_SIZE[1]))
        rect = image.get_rect(
            topleft=(round(x + (CARD_SIZE[0] - width) / 2), round(y))
        )
        pygame.draw.rect(
            self.frame, (8, 41, 28), rect.move(2, 4), border_radius=7
        )
        self.frame.blit(image, rect)

    def _message(self, table: Table) -> None:
        """Показать контекст текущего хода в центре стола."""
        hint = ""
        if table.phase is Phase.BET and table.balance >= CHIPS[0]:
            title = "Сделайте ставку"
            hint = "Выберите фишки, затем нажмите «Раздать»"
        elif table.phase is Phase.PLAYER:
            title = "Ваш ход"
        elif table.phase is Phase.DEALER:
            title = "Ход дилера"
        elif table.phase is Phase.RESULT:
            if len(table.hands) == 1 and table.hands[0].outcome is not None:
                title = OUTCOME_LABELS[table.hands[0].outcome][0]
            else:
                title = "Раунд завершён"
            hint = (
                f"Итог раунда {table.delta:+d}"
                if table.delta
                else "Ставка возвращена"
            )
            if not table.delta and len(table.hands) == 2:
                hint = "Без изменения баланса"
        else:
            title = "Фишки закончились"
            hint = "Начните новую сессию"

        box = pygame.Rect(0, 0, 412, 80)
        box.center = TABLE.centerx, 333
        pygame.draw.rect(self.frame, (15, 58, 42), box, border_radius=13)
        pygame.draw.rect(self.frame, (83, 126, 93), box, 1, 13)
        self._text(
            title,
            (box.centerx, box.centery - 12 if hint else box.centery),
            27,
            GOLD,
            center=True,
            serif=True,
        )
        if hint:
            self._text(
                hint, (box.centerx, box.centery + 18), 17, WHITE, center=True
            )

    def _panel(self, table: Table) -> None:
        """Показать сумму ставки и статистику текущей сессии."""
        pygame.draw.rect(self.frame, SURFACE, PANEL, border_radius=22)
        pygame.draw.rect(self.frame, EDGE, PANEL, 1, 22)
        x = PANEL.left + 25
        y = PANEL.top + 28
        self._text("Ставка", (x, y), 18, MUTED, bold=True)
        amount = (
            table.bet
            if table.phase is Phase.BET
            else sum(h.stake for h in table.hands)
        )
        self._text(str(amount), (x, y + 28), 43, GOLD, serif=True)
        self._text("фишек", (x, y + 84), 16, MUTED)
        self._divider(y + 128)
        self._text("Статистика сессии", (x, y + 151), 20, WHITE, bold=True)
        for i, (label, value, color) in enumerate(
            (
                ("Раунды", table.rounds, WHITE),
                ("Победы", table.wins, GREEN),
                ("Ничьи", table.pushes, GOLD),
                ("Проигрыши", table.losses, RED),
            )
        ):
            row = y + 192 + i * 36
            self._text(label, (x, row), 18, MUTED)
            number = self._font(18, bold=True).render(str(value), True, color)
            self.frame.blit(
                number, number.get_rect(topright=(PANEL.right - 24, row))
            )

        self._divider(y + 345)
        self._text("Условия стола", (x, y + 368), 19, WHITE, bold=True)
        self._text("Блэкджек оплачивается 3 к 2", (x, y + 405), 16, MUTED)
        self._text("Дилер останавливается на 17", (x, y + 435), 16, MUTED)

    def _divider(self, y: int) -> None:
        """Отделить блоки информации на правой панели."""
        pygame.draw.line(
            self.frame, EDGE, (PANEL.left + 25, y), (PANEL.right - 25, y)
        )

    def _footer(self, table: Table) -> None:
        """Нарисовать основание для фишек и игровых действий."""
        pygame.draw.rect(self.frame, SURFACE, FOOTER, border_radius=18)
        pygame.draw.rect(self.frame, EDGE, FOOTER, 1, 18)
        titles = {
            Phase.BET: "Фишки",
            Phase.PLAYER: "Ваш ход",
            Phase.DEALER: "Ход дилера",
            Phase.RESULT: "Раунд завершён",
        }
        self._text(titles[table.phase], (49, 670), 19, MUTED, bold=True)

    def _button(self, button: Button, hovered: bool) -> None:
        """Нарисовать кнопку действия или круглый номинал фишки."""
        if isinstance(button.intent, int):
            self._chip(button, hovered)
            return
        if not button.enabled:
            color, foreground, outline = (29, 46, 38), (153, 171, 159), EDGE
        elif button.primary:
            color = (246, 216, 157) if hovered else GOLD
            foreground, outline = INK, color
        else:
            color = (53, 76, 63) if hovered else (30, 52, 43)
            foreground, outline = WHITE, (119, 147, 129) if hovered else EDGE
        pygame.draw.rect(self.frame, color, button.rect, border_radius=11)
        pygame.draw.rect(self.frame, outline, button.rect, 1, 11)
        self._text(
            button.label,
            button.rect.center,
            18,
            foreground,
            center=True,
            bold=True,
        )

    def _chip(self, button: Button, hovered: bool) -> None:
        """Сочетать цвет номинала, насечки и подпись фишки."""
        center = button.rect.center
        color = (
            CHIP_COLORS[int(button.intent)] if button.enabled else (58, 74, 66)
        )
        ring = GOLD if hovered and button.enabled else (195, 207, 185)
        pygame.draw.circle(
            self.frame, (11, 24, 19), (center[0], center[1] + 3), 27
        )
        pygame.draw.circle(self.frame, color, center, 26)
        pygame.draw.circle(self.frame, ring, center, 25, 1)
        pygame.draw.circle(self.frame, ring, center, 18, 1)
        for angle in range(0, 360, 60):
            direction = pygame.Vector2(1, 0).rotate(angle)
            point = pygame.Vector2(center)
            pygame.draw.line(
                self.frame,
                ring,
                point + direction * 19,
                point + direction * 25,
                3,
            )
        self._text(button.label, center, 17, WHITE, center=True, bold=True)

    def _rules(self) -> None:
        """Показать подсказку с правилами и доступными действиями."""
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((3, 10, 8, 190))
        self.frame.blit(dim, (0, 0))
        area = pygame.Rect(274, 141, 612, 458)
        pygame.draw.rect(self.frame, (23, 42, 33), area, border_radius=22)
        pygame.draw.rect(self.frame, GOLD_DARK, area, 1, 22)
        self._text("Правила стола", (306, 170), 36, GOLD, serif=True)
        sections = (
            ("Цель", "Набрать больше дилера, не выходя за 21."),
            ("Карты", "Валет, дама и король дают 10. Туз даёт 1 или 11."),
            ("Действия", "Удвоение даёт одну карту. Пару можно разделить."),
            ("Дилер", "Берёт до 16 включительно. Останавливается на 17."),
            ("Выплаты", "Блэкджек — 3 к 2. Победа — 1 к 1. Ничья — возврат."),
        )
        for i, (title, line) in enumerate(sections):
            y = 228 + i * 57
            self._text(title, (307, y), 17, WHITE, bold=True)
            self._text(line, (307, y + 22), 17, MUTED)
