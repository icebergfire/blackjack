"""Запуск окна «Блэкджека» и обработка действий игрока."""

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from game import CHIPS, Action, Phase, Table
from graphics import HEIGHT, WIDTH, Intent, TableView, viewport

# Управление клавиатурой использует цифры в порядке фишек на столе.
CHIP_KEYS = dict(zip((pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4), CHIPS))
FPS = 60


def logical_position(
    position: tuple[int, int], box: pygame.Rect
) -> tuple[float, float]:
    """Преобразовать координаты мыши в координаты игрового полотна."""
    return (position[0] - box.left) * WIDTH / box.width, (
        position[1] - box.top
    ) * HEIGHT / box.height


def keyboard_action(
    key: int, phase: Phase, rules: bool, can_bet: bool
) -> Intent | None:
    """Вернуть команду горячей клавиши, подходящую для текущего экрана."""
    if rules:
        return "close" if key in (pygame.K_ESCAPE, pygame.K_RETURN) else None
    if key == pygame.K_F1:
        return "rules"
    if key == pygame.K_ESCAPE:
        return "quit"
    if phase is Phase.BET:
        if key == pygame.K_RETURN:
            return "deal" if can_bet else "reset"
        return CHIP_KEYS.get(key)
    if phase is Phase.RESULT and key == pygame.K_RETURN:
        return "next"
    if phase is Phase.PLAYER:
        return {pygame.K_SPACE: Action.HIT, pygame.K_RETURN: Action.STAND}.get(
            key
        )
    return None


def run() -> None:
    """Открыть окно и обновлять стол до завершения игры."""
    pygame.display.set_caption("Блэкджек")
    pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    table = Table()
    view = TableView()
    clock = pygame.time.Clock()
    now = 0.0
    rules = False
    while True:
        now += min(clock.tick(FPS), 100) / 1000
        window = pygame.display.get_surface()
        box = viewport(window.get_size())
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

            buttons = view.buttons(table, now, rules)
            if event.type == pygame.KEYDOWN:
                intent = keyboard_action(
                    event.key, table.phase, rules, table.balance >= CHIPS[0]
                )
                if intent == "quit":
                    return
                if not any(
                    button.intent == intent and button.enabled
                    for button in buttons
                ):
                    continue
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                point = logical_position(event.pos, box)
                intent = next(
                    (
                        button.intent
                        for button in buttons
                        if button.enabled and button.rect.collidepoint(point)
                    ),
                    None,
                )
            else:
                continue

            if intent == "rules":
                rules = True
            elif intent == "close":
                rules = False
            elif intent == "reset":
                table = Table()
            elif isinstance(intent, int):
                table.add_chip(intent)
            elif isinstance(intent, Action):
                table.play(intent)
            elif intent == "deal":
                table.deal()
            elif intent == "next":
                table.next_round()
            elif intent == "clear":
                table.clear_bet()
            view.sync(table, now)

        if table.phase is Phase.DEALER and not rules and not view.busy(now):
            table.advance_dealer()
        view.sync(table, now)
        point = logical_position(pygame.mouse.get_pos(), box)
        frame = view.render(table, now, point, rules)
        window.fill((8, 17, 13))
        window.blit(
            frame
            if box.size == frame.get_size()
            else pygame.transform.smoothscale(frame, box.size),
            box,
        )
        pygame.display.flip()


def main() -> None:
    """Подготовить графику и освободить ресурсы после закрытия окна."""
    pygame.display.init()
    pygame.font.init()
    try:
        run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
