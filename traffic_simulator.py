"""Four-Way Traffic Signal Simulator — Python + Pygame.

Controls:
  Click a signal button to change it
  Space: pause/resume   R: reset   Up/Down: change speed   Esc: quit

Install dependency: python3 -m pip install pygame
Run: python3 traffic_simulator.py
"""
import math
import random
import sys
import pygame

SW, SH = 1100, 720
MAX_VEHICLES = 32
SPAWN_INTERVAL = 850  # milliseconds
STOP_GAP = 12
FOLLOW_GAP = 18

RED, YELLOW, GREEN = 0, 1, 2
NORTH_SOUTH, SOUTH_NORTH, WEST_EAST, EAST_WEST = 0, 1, 2, 3
NAMES = ["NORTH TO SOUTH", "SOUTH TO NORTH", "WEST TO EAST", "EAST TO WEST"]

ROAD = (54, 58, 63)
EDGE = (155, 157, 145)
WHITE = (239, 238, 225)
DARK = (24, 31, 35)
PANEL = (32, 45, 51)
TEXT = (232, 236, 231)
MUTED = (155, 173, 172)
RED_C = (219, 66, 64)
YELLOW_C = (239, 190, 65)
GREEN_C = (66, 184, 105)
CYAN = (50, 210, 230)
PALETTE = [(215,220,217), (62,132,188), (177,72,64),
           (76,143,95), (206,160,75), (103,91,143)]
SIGNAL_COLORS = [RED_C, YELLOW_C, GREEN_C]


def is_vertical(direction):
    return direction < 2


def lane_pos(direction, lane):
    return {
        NORTH_SOUTH: (455 if lane else 415),
        SOUTH_NORTH: (645 if lane else 605),
        WEST_EAST: (300 if lane else 340),
        EAST_WEST: (420 if lane else 460),
    }[direction]


def stop_line(direction):
    return {
        NORTH_SOUTH: 208,
        SOUTH_NORTH: 512,
        WEST_EAST: 358,
        EAST_WEST: 742,
    }[direction]


class Vehicle:
    def __init__(self, direction, lane, kind, x, y, w, h, speed, color):
        self.active = True
        self.direction = direction
        self.lane = lane
        self.kind = kind  # car, bus, truck, auto-rickshaw, motorcycle, scooter
        self.x, self.y = float(x), float(y)
        self.w, self.h = w, h
        self.speed = speed
        self.color = color

    @staticmethod
    def dimensions(kind, vertical):
        if vertical:
            w = 13 if kind in (4, 5) else 21 if kind == 3 else 29
            h = 70 if kind == 1 else 66 if kind == 2 else 36 if kind == 3 else 42
        else:
            w = 70 if kind == 1 else 66 if kind == 2 else 36 if kind == 3 else 42
            h = 13 if kind in (4, 5) else 21 if kind == 3 else 29
        return w, h


class TrafficSimulator:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Four-Way Traffic Signal Simulator")
        self.screen = pygame.display.set_mode((SW, SH))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("menlo", 15, bold=True)
        self.small_font = pygame.font.SysFont("menlo", 12, bold=True)
        self.signals = [RED, RED, GREEN, GREEN]
        self.cars = []
        self.buttons = {}
        self.running = True
        self.paused = False
        self.passed = 0
        self.speed_factor = 1.0
        self.last_spawn = pygame.time.get_ticks()
        self.configure_buttons()

    def configure_buttons(self):
        for st in range(3):
            self.buttons[(NORTH_SOUTH, st)] = pygame.Rect(25, 50 + st * 28, 285, 24)
            self.buttons[(EAST_WEST, st)] = pygame.Rect(786, 50 + st * 28, 285, 24)
            self.buttons[(WEST_EAST, st)] = pygame.Rect(25, 557 + st * 28, 285, 24)
            self.buttons[(SOUTH_NORTH, st)] = pygame.Rect(786, 557 + st * 28, 285, 24)

    def set_signal(self, direction, state):
        # Opposing directions may share green; perpendicular directions may not.
        if state == GREEN:
            if is_vertical(direction):
                self.signals[WEST_EAST] = RED
                self.signals[EAST_WEST] = RED
            else:
                self.signals[NORTH_SOUTH] = RED
                self.signals[SOUTH_NORTH] = RED
        self.signals[direction] = state

    def reset(self):
        self.cars.clear()
        self.signals = [RED, RED, GREEN, GREEN]
        self.passed = 0
        self.paused = False
        self.last_spawn = pygame.time.get_ticks()

    def spawn(self):
        if len(self.cars) >= MAX_VEHICLES:
            return
        for _ in range(20):
            d, lane, kind = random.randrange(4), random.randrange(2), random.randrange(6)
            vertical = is_vertical(d)
            w, h = Vehicle.dimensions(kind, vertical)
            x = lane_pos(d, lane) if vertical else (-55 if d == WEST_EAST else SW + 55)
            y = (-50 if d == NORTH_SOUTH else SH + 50) if vertical else lane_pos(d, lane)
            clear = True
            for other in self.cars:
                if other.direction != d or other.lane != lane:
                    continue
                distance = abs(other.y - y) if vertical else abs(other.x - x)
                required = ((other.h + h) / 2 + 35) if vertical else ((other.w + w) / 2 + 35)
                if distance < required:
                    clear = False
                    break
            if clear:
                self.cars.append(Vehicle(d, lane, kind, x, y, w, h,
                                         1.1 + random.randrange(75) / 100,
                                         random.choice(PALETTE)))
                return

    def update(self, dt):
        multiplier = min((dt / 16.0) * self.speed_factor, 2.5)
        for v in list(self.cars):
            vertical = is_vertical(v.direction)
            pos = v.y if vertical else v.x
            direction = 1 if v.direction in (NORTH_SOUTH, WEST_EAST) else -1
            half = v.h / 2 if vertical else v.w / 2
            next_pos = pos + direction * v.speed * multiplier
            stop = stop_line(v.direction)

            if self.signals[v.direction] != GREEN:
                if direction > 0 and pos < stop and next_pos + half > stop - STOP_GAP:
                    next_pos = stop - STOP_GAP - half
                elif direction < 0 and pos > stop and next_pos - half < stop + STOP_GAP:
                    next_pos = stop + STOP_GAP + half

            # Only the nearest vehicle ahead in the same lane is a leader.
            leader = None
            leader_pos = math.inf if direction > 0 else -math.inf
            for other in self.cars:
                if other is v or not other.active:
                    continue
                if other.direction != v.direction or other.lane != v.lane:
                    continue
                op = other.y if vertical else other.x
                if direction > 0 and pos < op < leader_pos:
                    leader, leader_pos = other, op
                elif direction < 0 and pos > op > leader_pos:
                    leader, leader_pos = other, op

            if leader is not None:
                leader_half = leader.h / 2 if vertical else leader.w / 2
                limit = leader_pos - direction * (leader_half + half + FOLLOW_GAP)
                if direction > 0:
                    next_pos = min(next_pos, max(pos, limit))
                else:
                    next_pos = max(next_pos, min(pos, limit))

            if vertical:
                v.y = next_pos
            else:
                v.x = next_pos

            if ((v.direction == NORTH_SOUTH and v.y - v.h / 2 > SH) or
                (v.direction == SOUTH_NORTH and v.y + v.h / 2 < 0) or
                (v.direction == WEST_EAST and v.x - v.w / 2 > SW) or
                (v.direction == EAST_WEST and v.x + v.w / 2 < 0)):
                v.active = False
                self.passed += 1
        self.cars = [v for v in self.cars if v.active]

    def draw_text(self, x, y, value, color=TEXT, small=False):
        font = self.small_font if small else self.font
        self.screen.blit(font.render(str(value), True, color), (x, y))

    def rect(self, x, y, w, h, color):
        pygame.draw.rect(self.screen, color, (int(x), int(y), int(w), int(h)))

    def outline(self, x, y, w, h, color):
        pygame.draw.rect(self.screen, color, (int(x), int(y), int(w), int(h)), 1)

    def draw_road(self):
        self.screen.fill((29, 39, 43))
        self.rect(370, 0, 360, SH, ROAD)
        self.rect(0, 220, SW, 280, ROAD)
        self.rect(358, 0, 12, SH, EDGE)
        self.rect(730, 0, 12, SH, EDGE)
        self.rect(0, 208, SW, 12, EDGE)
        self.rect(0, 500, SW, 12, EDGE)
        for y in list(range(0, 208, 42)) + list(range(512, SH, 42)):
            for x in (425, 505, 585, 665):
                self.rect(x, y + 8, 3, 22, WHITE)
        for x in list(range(0, 358, 42)) + list(range(742, SW, 42)):
            for y in (280, 435):
                self.rect(x + 8, y, 22, 3, WHITE)
        self.rect(370, 220, 360, 4, WHITE)
        self.rect(370, 496, 360, 4, WHITE)
        self.rect(370, 220, 4, 280, WHITE)
        self.rect(726, 220, 4, 280, WHITE)
        for i in range(10):
            self.rect(380 + i * 34, 228, 20, 18, WHITE)
            self.rect(380 + i * 34, 474, 20, 18, WHITE)
        for i in range(7):
            for x in (8 + i * 45, 750 + i * 48):
                self.rect(x, 228, 22, 18, WHITE)
                self.rect(x, 474, 22, 18, WHITE)

    def draw_vehicle(self, v):
        x, y, w, h = round(v.x), round(v.y), v.w, v.h
        glass = (105, 164, 185)
        tire = (18, 21, 23)
        vertical = is_vertical(v.direction)
        if v.kind in (4, 5):  # motorcycle / scooter
            if vertical:
                pygame.draw.circle(self.screen, tire, (x, y - h // 3), 3)
                pygame.draw.circle(self.screen, tire, (x, y + h // 3), 3)
                self.rect(x - 3, y - h // 4, 6, h // 2,
                          v.color if v.kind == 4 else (230, 184, 87))
                pygame.draw.circle(self.screen, (35, 39, 42), (x, y - 2), 3)
            else:
                pygame.draw.circle(self.screen, tire, (x - w // 3, y), 3)
                pygame.draw.circle(self.screen, tire, (x + w // 3, y), 3)
                self.rect(x - w // 4, y - 3, w // 2, 6,
                          v.color if v.kind == 4 else (230, 184, 87))
            return

        self.rect(x - w//2 + 2, y - h//2 + 3, w, h, (18, 21, 23))
        self.rect(x - w//2, y - h//2, w, h, v.color)
        if v.kind == 3:  # auto-rickshaw
            if vertical:
                self.rect(x-w//2+3, y-h//2+4, w-6, max(3,h//3), (228,190,77))
                self.rect(x-w//2+4, y-h//2+7, w-8, 6, (43,53,52))
                self.rect(x-w//2+4, y+2, w-8, max(3,h//4), glass)
            else:
                self.rect(x-w//2+4, y-h//2+3, max(3,w//3), h-6, (228,190,77))
                self.rect(x-w//2+6, y-h//2+4, 6, h-8, (43,53,52))
                self.rect(x+3, y-h//2+4, max(3,w//4), h-8, glass)
        elif v.kind == 1:  # bus
            if vertical:
                for k in range(4): self.rect(x-w//2+4, y-h//2+8+k*13, w-8, 8, glass)
            else:
                for k in range(4): self.rect(x-w//2+8+k*13, y-h//2+4, 8, h-8, glass)
        elif v.kind == 2:  # truck
            if vertical:
                self.rect(x-w//2+3, y-h//2+3, w-6, h*2//3, (170,177,174))
                for k in range(5):
                    pygame.draw.line(self.screen, (105,114,113),
                                     (x-w//2+4, y-h//2+7+k*8), (x+w//2-4, y-h//2+7+k*8))
                self.rect(x-w//2+4, y+h//2-h//3, w-8, max(3,h//4), (66,130,174))
            else:
                self.rect(x-w//2+3, y-h//2+3, w*2//3, h-6, (170,177,174))
                for k in range(5):
                    pygame.draw.line(self.screen, (105,114,113),
                                     (x-w//2+7+k*8, y-h//2+4), (x-w//2+7+k*8, y+h//2-4))
                self.rect(x+w//2-w//3, y-h//2+4, max(3,w//4), h-8, (66,130,174))
        else:  # passenger car
            if vertical:
                self.rect(x-w//2+4, y-h//2+7, w-8, max(3,h//4), glass)
                self.rect(x-w//2+4, y+2, w-8, max(3,h//4), glass)
            else:
                self.rect(x-w//2+7, y-h//2+4, max(3,w//4), h-8, glass)
                self.rect(x+2, y-h//2+4, max(3,w//4), h-8, glass)

    def draw_signal_button(self, direction, state):
        r = self.buttons[(direction, state)]
        lamp = SIGNAL_COLORS[state]
        bg = DARK
        if self.signals[direction] == state:
            bg = [(130,45,45), (118,92,32), (35,100,62)][state]
        pygame.draw.rect(self.screen, bg, r)
        pygame.draw.rect(self.screen, lamp if self.signals[direction] == state else (90,100,102), r, 1)
        pygame.draw.circle(self.screen, lamp, (r.x + 14, r.y + r.h//2), 6)
        label = ["RED - STOP", "YELLOW - WAIT", "GREEN - GO"][state]
        self.draw_text(r.x + 32, r.y + 4, label, TEXT, small=True)

    def draw_panel(self):
        cards = [(12,10,315,185), (773,10,315,185),
                 (12,515,315,190), (773,515,315,190)]
        for x,y,w,h in cards:
            self.rect(x,y,w,h,PANEL)
            self.outline(x,y,w,h,(65,91,96))
        self.draw_text(25, 20, NAMES[NORTH_SOUTH])
        self.draw_text(786, 20, NAMES[EAST_WEST])
        self.draw_text(25, 525, NAMES[WEST_EAST])
        self.draw_text(786, 525, NAMES[SOUTH_NORTH])
        for state in range(3):
            for d in range(4):
                self.draw_signal_button(d, state)

    def draw_road_signal(self, direction, x, y):
        self.rect(x-13, y-8, 26, 70, (16,20,22))
        self.outline(x-13, y-8, 26, 70, (105,113,111))
        for state in range(3):
            color = SIGNAL_COLORS[state] if self.signals[direction] == state else (65,69,66)
            pygame.draw.circle(self.screen, color, (x, y + state*21), 7)

    def draw_stats(self):
        counts = [0, 0, 0, 0]
        for v in self.cars:
            counts[v.direction] += 1
        total = len(self.cars)
        self.draw_text(25, 665, f"ON ROAD: {total}", CYAN, small=True)
        self.draw_text(25, 679, f"N-S {counts[0]}  S-N {counts[1]}", TEXT, small=True)
        self.draw_text(786, 665, f"W-E {counts[2]}  E-W {counts[3]}", TEXT, small=True)
        self.draw_text(786, 679, f"PASSED: {self.passed}", GREEN_C, small=True)
        self.draw_text(480, 680, f"SPEED {self.speed_factor:.2f}x" + ("  PAUSED" if self.paused else ""), MUTED, small=True)

    def render(self):
        self.draw_road()
        for v in self.cars:
            self.draw_vehicle(v)
        self.draw_road_signal(NORTH_SOUTH, 755, 185)
        self.draw_road_signal(SOUTH_NORTH, 345, 535)
        self.draw_road_signal(WEST_EAST, 340, 185)
        self.draw_road_signal(EAST_WEST, 760, 535)
        self.draw_panel()
        self.draw_stats()
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = min(self.clock.tick(60), 50)
            now = pygame.time.get_ticks()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Window and logical resolution are identical, so event coordinates map directly.
                    for (direction, state), rect in self.buttons.items():
                        if rect.collidepoint(event.pos):
                            self.set_signal(direction, state)
                            break
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_SPACE:
                        self.paused = not self.paused
                    elif event.key == pygame.K_r:
                        self.reset()
                    elif event.key == pygame.K_UP:
                        self.speed_factor = min(2.5, self.speed_factor + 0.25)
                    elif event.key == pygame.K_DOWN:
                        self.speed_factor = max(0.5, self.speed_factor - 0.25)

            if not self.paused:
                if now - self.last_spawn >= SPAWN_INTERVAL:
                    self.spawn()
                    self.last_spawn = now
                self.update(dt)
            self.render()

        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    TrafficSimulator().run()
