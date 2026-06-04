import pygame
import sys
import math
import random
import array

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

# ==================== CONSTANTS ====================
SW, SH = 900, 550
FPS = 60
GRAVITY = 0.5
JUMP_FORCE = -13
SPEED = 4.5

BLACK   = (0,   0,   0)
WHITE   = (255, 255, 255)
DARK    = (8,   8,   12)
DGRAY   = (28,  28,  38)
MGRAY   = (50,  50,  62)
GRAY    = (75,  75,  90)
LGRAY   = (140, 140, 155)
RED     = (160, 20,  20)
DRED    = (90,  0,   0)

screen = pygame.display.set_mode((SW, SH))
pygame.display.set_caption("BLACK BOY")
clock  = pygame.time.Clock()

F_SM = pygame.font.SysFont("Arial", 17)
F_MD = pygame.font.SysFont("Arial", 26, bold=True)
F_LG = pygame.font.SysFont("Arial", 48, bold=True)
F_XL = pygame.font.SysFont("Arial", 80, bold=True)


# ==================== SOUND ====================
def _sine(t, freq, env=1.0):
    return math.sin(2 * math.pi * freq * t) * env

def make_sound(gen_func, duration, vol=0.5, rate=44100):
    n = int(rate * duration)
    buf = array.array('h', [0] * n)
    for i in range(n):
        t = i / rate
        v = gen_func(t, i, n)
        v = max(-1.0, min(1.0, v))
        buf[i] = int(v * 32767 * vol)
    return pygame.sndarray.make_sound(buf)

def gen_jump(t, i, n):
    p = i / n
    return _sine(t, 220 + 300 * p) * math.exp(-4 * p)

def gen_land(t, i, n):
    p = i / n
    noise = random.uniform(-1, 1) * 0.5
    return (_sine(t, 100 * (1 - p)) * 0.5 + noise * 0.5) * math.exp(-10 * p)

def gen_death(t, i, n):
    p = i / n
    noise = random.uniform(-1, 1) * 0.3
    return (_sine(t, 400 * (1 - p * 0.6)) + noise) * math.exp(-2.5 * p)

def gen_checkpoint(t, i, n):
    p = i / n
    notes = [523, 659, 784]
    freq = notes[min(int(p * 3), 2)]
    lp = (p * 3) % 1.0
    return _sine(t, freq) * math.exp(-5 * lp)

def gen_lever(t, i, n):
    p = i / n
    return (_sine(t, 280) * 0.6 + _sine(t, 560) * 0.3 +
            random.uniform(-1, 1) * 0.1) * (1 - p)

def gen_win(t, i, n):
    p = i / n
    melody = [523, 659, 784, 1047]
    freq = melody[min(int(p * 4), 3)]
    lp = (p * 4) % 1.0
    return _sine(t, freq) * math.sin(math.pi * lp) * math.exp(-p * 0.4)

def gen_ambient(t, i, n):
    return (_sine(t, 55) * 0.4 + _sine(t, 82) * 0.25 +
            random.uniform(-1, 1) * 0.04)

SND = {}
try:
    SND['jump']       = make_sound(gen_jump,       0.25, 0.45)
    SND['land']       = make_sound(gen_land,       0.18, 0.35)
    SND['death']      = make_sound(gen_death,      0.65, 0.50)
    SND['checkpoint'] = make_sound(gen_checkpoint, 0.45, 0.45)
    SND['lever']      = make_sound(gen_lever,      0.30, 0.40)
    SND['win']        = make_sound(gen_win,        1.20, 0.50)
    SND['ambient']    = make_sound(gen_ambient,    4.00, 0.12)
except Exception as e:
    print("Sound warning:", e)

def play(name, loops=0):
    if name in SND:
        try: SND[name].play(loops=loops)
        except: pass

def stop(name):
    if name in SND:
        try: SND[name].stop()
        except: pass


# ==================== PARTICLES ====================
class Particle:
    def __init__(self, x, y, color, life=45):
        self.x, self.y = float(x), float(y)
        self.vx = random.uniform(-2.5, 2.5)
        self.vy = random.uniform(-4.0, -0.5)
        self.color = color
        self.life = life
        self.max_life = life
        self.size = random.randint(2, 5)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.18
        self.life -= 1

    def draw(self, surf, cam):
        a = self.life / self.max_life
        c = tuple(max(0, min(255, int(ch * a))) for ch in self.color)
        s = max(1, int(self.size * a))
        pygame.draw.circle(surf, c, (int(self.x - cam), int(self.y)), s)

class Particles:
    def __init__(self): self.list = []

    def emit(self, x, y, n=10, color=WHITE, life=45):
        for _ in range(n):
            self.list.append(Particle(x, y, color,
                             life + random.randint(-8, 8)))

    def update(self):
        self.list = [p for p in self.list if p.life > 0]
        for p in self.list: p.update()

    def draw(self, surf, cam):
        for p in self.list: p.draw(surf, cam)

    def clear(self): self.list.clear()


# ==================== PLAYER ====================
class Player:
    def __init__(self, x, y):
        self.spawn_x, self.spawn_y = x, y
        self.rect = pygame.Rect(x, y, 28, 48)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.prev_ground = False
        self.alive = True
        self.death_timer = 0
        self.facing = 1
        self.walk_t = 0.0
        self.coyote = 0
        self.jbuf = 0

    def handle_input(self):
        keys = pygame.key.get_pressed()
        tx = 0
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: tx = -SPEED; self.facing = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: tx =  SPEED; self.facing =  1
        self.vx += (tx - self.vx) * 0.22

        if keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]:
            self.jbuf = 8
        else:
            self.jbuf = max(0, self.jbuf - 1)

        if self.jbuf > 0 and self.coyote > 0:
            self.vy = JUMP_FORCE
            self.on_ground = False
            self.coyote = 0
            self.jbuf = 0
            play('jump')

    def move(self, plats, parts):
        # X
        self.rect.x += int(self.vx)
        for p in plats:
            if self.rect.colliderect(p.rect):
                if self.vx > 0: self.rect.right = p.rect.left
                else:           self.rect.left  = p.rect.right
                self.vx = 0

        # Y
        self.prev_ground = self.on_ground
        self.on_ground = False
        self.rect.y += int(self.vy)
        for p in plats:
            if self.rect.colliderect(p.rect):
                if self.vy > 0:
                    self.rect.bottom = p.rect.top
                    self.on_ground = True
                    if not self.prev_ground and self.vy > 4:
                        play('land')
                        parts.emit(self.rect.centerx, self.rect.bottom,
                                   n=5, color=GRAY, life=22)
                    self.vy = 0
                else:
                    self.rect.top = p.rect.bottom
                    self.vy = 0

        # Moving platform carry
        for p in plats:
            if hasattr(p, 'dx') and self.on_ground and \
               self.rect.bottom <= p.rect.top + 6 and \
               self.rect.colliderect(p.rect):
                self.rect.x += p.dx
                self.rect.y += p.dy

        self.coyote = 8 if self.on_ground else max(0, self.coyote - 1)
        if self.on_ground and abs(self.vx) > 0.5:
            self.walk_t += 0.18

    def update(self, plats, parts):
        if not self.alive:
            self.death_timer -= 1
            return
        self.handle_input()
        self.vy = min(self.vy + GRAVITY, 18)
        self.move(plats, parts)
        if self.rect.top > SH + 120:
            self.die(parts)

    def die(self, parts):
        if not self.alive: return
        self.alive = False
        self.death_timer = 100
        play('death')
        parts.emit(self.rect.centerx, self.rect.centery,
                   n=22, color=DRED, life=65)

    def draw(self, surf, cam, tick):
        if not self.alive: return
        dx = self.rect.x - cam
        dy = self.rect.y
        b  = math.sin(tick * 0.05) * 1.5

        # Shadow
        sh = pygame.Surface((32, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 70), (0, 0, 32, 10))
        surf.blit(sh, (dx - 2, self.rect.bottom - 6))

        # Body
        pygame.draw.ellipse(surf, BLACK,
                            (dx + 4, dy + 17 + b, 20, 27))
        # Head
        pygame.draw.circle(surf, BLACK, (dx + 14, dy + 10 + int(b)), 13)

        # Eye
        eo = 4 * self.facing
        pygame.draw.circle(surf, WHITE,  (dx + 14 + eo, dy +  8 + int(b)), 5)
        pygame.draw.circle(surf, BLACK,  (dx + 15 + eo, dy +  8 + int(b)), 3)
        pygame.draw.circle(surf, WHITE,  (dx + 16 + eo, dy +  6 + int(b)), 1)

        # Legs
        if self.on_ground and abs(self.vx) > 0.5:
            sw = math.sin(self.walk_t) * 9
            pygame.draw.line(surf, BLACK, (dx+10, dy+40), (dx+7+int(sw),  dy+48), 4)
            pygame.draw.line(surf, BLACK, (dx+18, dy+40), (dx+21-int(sw), dy+48), 4)
        else:
            pygame.draw.line(surf, BLACK, (dx+10, dy+40), (dx+8,  dy+48), 4)
            pygame.draw.line(surf, BLACK, (dx+18, dy+40), (dx+20, dy+48), 4)

        # Arms
        aw = math.sin(self.walk_t) * 5 if self.on_ground else 0
        pygame.draw.line(surf, BLACK, (dx+6,  dy+22), (dx+2,  dy+32+int(aw)),  3)
        pygame.draw.line(surf, BLACK, (dx+22, dy+22), (dx+26, dy+32-int(aw)),  3)


# ==================== GAME OBJECTS ====================
class Platform:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)
        self.dx = 0; self.dy = 0

    def draw(self, surf, cam):
        r = pygame.Rect(self.rect.x - cam, self.rect.y,
                        self.rect.width, self.rect.height)
        pygame.draw.rect(surf, DGRAY, r)
        pygame.draw.rect(surf, MGRAY, r, 1)
        pygame.draw.line(surf, GRAY, (r.left+1, r.top+1), (r.right-2, r.top+1))


class MovingPlatform:
    def __init__(self, x, y, w, h, pts, spd=1.8):
        self.rect  = pygame.Rect(x, y, w, h)
        self.pts   = pts
        self.cidx  = 0
        self.spd   = spd
        self.dx    = 0; self.dy = 0
        self._px   = float(x); self._py = float(y)

    def update(self):
        px, py = self._px, self._py
        tx, ty = self.pts[self.cidx]
        d = math.hypot(tx - self._px, ty - self._py)
        if d < self.spd + 1:
            self._px, self._py = float(tx), float(ty)
            self.cidx = (self.cidx + 1) % len(self.pts)
        else:
            self._px += (tx - self._px) / d * self.spd
            self._py += (ty - self._py) / d * self.spd
        self.dx = int(self._px - px)
        self.dy = int(self._py - py)
        self.rect.x = int(self._px)
        self.rect.y = int(self._py)

    def draw(self, surf, cam):
        r = pygame.Rect(self.rect.x - cam, self.rect.y,
                        self.rect.width, self.rect.height)
        pygame.draw.rect(surf, MGRAY, r)
        pygame.draw.rect(surf, LGRAY, r, 1)
        pygame.draw.circle(surf, GRAY, r.center, 4)


class FallingPlatform:
    def __init__(self, x, y, w, h):
        self.rect   = pygame.Rect(x, y, w, h)
        self.orig_y = y
        self.vy     = 0.0
        self.shake  = 0
        self.timer  = -1   # -1 = not triggered
        self.active = True
        self.dx     = 0; self.dy = 0

    def update(self, player):
        if not self.active: return
        prev_y = self.rect.y
        touching = (self.rect.colliderect(player.rect) and
                    player.rect.bottom <= self.rect.top + 8 and
                    player.vy >= 0)
        if touching and self.timer == -1:
            self.timer = 55
        if self.timer > 0:
            self.timer -= 1
            self.shake = random.randint(-2, 2) if self.timer < 35 else 0
        if self.timer == 0:
            self.vy += 0.9
            self.rect.y += int(self.vy)
        if self.rect.y > SH + 100:
            self.active = False
        self.dy = self.rect.y - prev_y
        self.dx = 0

    def draw(self, surf, cam):
        if not self.active: return
        r = pygame.Rect(self.rect.x - cam + self.shake, self.rect.y,
                        self.rect.width, self.rect.height)
        col = (75, 35, 35) if self.timer is not None and self.timer >= 0 else MGRAY
        pygame.draw.rect(surf, col, r)
        pygame.draw.rect(surf, LGRAY, r, 1)


class Spike:
    def __init__(self, x, y, count, direction='up'):
        self.x, self.y = x, y
        self.count = count
        self.dir   = direction
        w = count * 18
        h = 18
        if direction == 'up':
            self.rect = pygame.Rect(x, y - h, w, h)
        else:
            self.rect = pygame.Rect(x, y, w, h)

    def draw(self, surf, cam):
        for i in range(self.count):
            sx = self.x + i * 18 - cam
            if self.dir == 'up':
                pts = [(sx, self.y), (sx+9, self.y-18), (sx+18, self.y)]
            else:
                pts = [(sx, self.y), (sx+9, self.y+18), (sx+18, self.y)]
            pygame.draw.polygon(surf, BLACK, pts)
            pygame.draw.polygon(surf, GRAY,  pts, 1)

    def kills(self, player):
        return self.rect.colliderect(player.rect)


class Saw:
    def __init__(self, x, y, r, pts, spd=2.0):
        self.pts  = pts
        self.cidx = 0
        self.spd  = spd
        self.r    = r
        self.x    = float(x)
        self.y    = float(y)
        self.angle = 0.0
        self.rect  = pygame.Rect(int(x)-r, int(y)-r, r*2, r*2)

    def update(self):
        tx, ty = self.pts[self.cidx]
        d = math.hypot(tx - self.x, ty - self.y)
        if d < self.spd + 1:
            self.x, self.y = float(tx), float(ty)
            self.cidx = (self.cidx + 1) % len(self.pts)
        else:
            self.x += (tx - self.x) / d * self.spd
            self.y += (ty - self.y) / d * self.spd
        self.angle += 7
        self.rect = pygame.Rect(int(self.x)-self.r, int(self.y)-self.r,
                                self.r*2, self.r*2)

    def draw(self, surf, cam):
        cx = int(self.x) - cam
        cy = int(self.y)
        pygame.draw.circle(surf, DGRAY, (cx, cy), self.r)
        for i in range(14):
            a = math.radians(self.angle + i * (360/14))
            x1 = cx + int(math.cos(a) * (self.r - 3))
            y1 = cy + int(math.sin(a) * (self.r - 3))
            x2 = cx + int(math.cos(a) * (self.r + 6))
            y2 = cy + int(math.sin(a) * (self.r + 6))
            pygame.draw.line(surf, GRAY, (x1, y1), (x2, y2), 3)
        pygame.draw.circle(surf, BLACK,  (cx, cy), self.r, 2)
        pygame.draw.circle(surf, MGRAY,  (cx, cy), 5)

    def kills(self, player):
        return math.hypot(self.x - player.rect.centerx,
                          self.y - player.rect.centery) < self.r + 8


class Laser:
    def __init__(self, x1, y1, x2, y2, period=80):
        self.x1, self.y1 = x1, y1
        self.x2, self.y2 = x2, y2
        self.period = period
        self.t = 0
        self.on = True
        mn_x = min(x1, x2); mn_y = min(y1, y2)
        self.rect = pygame.Rect(mn_x, mn_y,
                                max(abs(x2-x1), 6), max(abs(y2-y1), 6))

    def update(self):
        self.t = (self.t + 1) % max(1, self.period)
        self.on = self.t < self.period // 2 if self.period > 0 else True

    def draw(self, surf, cam):
        if not self.on: return
        f = random.randint(210, 255)
        pygame.draw.line(surf, (f, f, f),
                         (self.x1-cam, self.y1), (self.x2-cam, self.y2), 3)
        pygame.draw.line(surf, WHITE,
                         (self.x1-cam, self.y1), (self.x2-cam, self.y2), 1)

    def kills(self, player):
        return self.on and self.rect.colliderect(player.rect)


class BouncePad:
    def __init__(self, x, y, w=64, power=17):
        self.rect  = pygame.Rect(x, y, w, 12)
        self.power = power
        self.anim  = 0

    def update(self, player, parts):
        if self.rect.colliderect(player.rect) and player.vy > 1:
            player.vy = -self.power
            self.anim = 14
            play('jump')
            parts.emit(self.rect.centerx, self.rect.top,
                       n=7, color=LGRAY, life=28)

    def draw(self, surf, cam):
        sq = self.anim * 0.35
        self.anim = max(0, self.anim - 1)
        r = pygame.Rect(self.rect.x - cam, self.rect.y + int(sq),
                        self.rect.width, max(4, 12 - int(sq)))
        pygame.draw.rect(surf, LGRAY, r)
        pygame.draw.rect(surf, WHITE, r, 2)
        cx = r.centerx
        pygame.draw.polygon(surf, WHITE,
                            [(cx, r.top-9), (cx-7, r.top), (cx+7, r.top)])


class Lever:
    def __init__(self, x, y, tid):
        self.x, self.y = x, y
        self.rect     = pygame.Rect(x-25, y-55, 70, 60)
        self.tid      = tid
        self.on       = False
        self.cooldown = 0

    def update(self, player, parts, doors):
        self.cooldown = max(0, self.cooldown - 1)
        keys = pygame.key.get_pressed()
        if (keys[pygame.K_e] or keys[pygame.K_f]) and \
           self.rect.colliderect(player.rect) and self.cooldown == 0:
            self.on = not self.on
            self.cooldown = 28
            play('lever')
            parts.emit(self.x, self.y - 20, n=7, color=WHITE, life=22)
            for d in doors:
                if d.tid == self.tid: d.toggle()

    def draw(self, surf, cam):
        dx = self.x - cam
        pygame.draw.rect(surf, GRAY, (dx-8, self.y-8, 20, 8))
        ang = -50 if self.on else 50
        ex = dx + 2 + int(math.cos(math.radians(ang)) * 26)
        ey = self.y - 8 + int(math.sin(math.radians(ang)) * 26)
        pygame.draw.line(surf, WHITE, (dx+2, self.y-8), (ex, ey), 4)
        pygame.draw.circle(surf, LGRAY, (ex, ey), 5)
        pygame.draw.rect(surf, MGRAY, (dx-8, self.y-8, 20, 8))
        if not self.on:
            h = F_SM.render("[E]", True, LGRAY)
            surf.blit(h, (dx-12, self.y-52))


class Door:
    def __init__(self, x, y, w, h, tid):
        self.orig_y = y
        self.rect   = pygame.Rect(x, y, w, h)
        self.tid    = tid
        self._cy    = float(y)
        self._ty    = float(y)
        self.open   = False

    def toggle(self):
        self.open = not self.open
        self._ty  = float(self.orig_y - self.rect.height) if self.open \
                    else float(self.orig_y)

    def update(self):
        diff = self._ty - self._cy
        if abs(diff) > 0.5: self._cy += diff * 0.09
        self.rect.y = int(self._cy)

    def draw(self, surf, cam):
        if self.open and abs(self._cy - self._ty) < 1.5: return
        r = pygame.Rect(self.rect.x - cam, int(self._cy),
                        self.rect.width, self.rect.height)
        pygame.draw.rect(surf, DGRAY, r)
        pygame.draw.rect(surf, GRAY,  r, 2)
        mh = r.height // 2 - 5
        pygame.draw.rect(surf, MGRAY, (r.left+4, r.top+4,    r.width-8, mh))
        pygame.draw.rect(surf, MGRAY, (r.left+4, r.centery+2, r.width-8, mh))


class Checkpoint:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.rect = pygame.Rect(x-8, y-50, 20, 52)
        self.active = False

    def check(self, player, parts):
        if not self.active and self.rect.colliderect(player.rect):
            self.active = True
            play('checkpoint')
            parts.emit(self.x, self.y-20, n=14, color=WHITE, life=55)
            return True
        return False

    def draw(self, surf, cam):
        dx = self.x - cam
        w  = math.sin(pygame.time.get_ticks() * 0.003) * 4 if self.active else 0
        col = WHITE if self.active else LGRAY
        pygame.draw.rect(surf, GRAY, (dx-2, self.y-50, 5, 50))
        pygame.draw.polygon(surf, col, [
            (dx+3, self.y-50+w), (dx+26, self.y-37+w), (dx+3, self.y-24+w)
        ])


class Goal:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 46, 80)
        self._t   = 0

    def update(self, parts):
        self._t += 1
        if self._t % 18 == 0:
            parts.emit(self.rect.centerx, self.rect.centery,
                       n=3, color=LGRAY, life=55)

    def draw(self, surf, cam):
        dx = self.rect.x - cam
        g  = abs(math.sin(self._t * 0.04)) * 35
        for i in range(3):
            sz = int(g * (3-i) * 0.28)
            if sz > 1:
                s = pygame.Surface((sz*2, sz*2), pygame.SRCALPHA)
                pygame.draw.circle(s, (255,255,255,18), (sz,sz), sz)
                surf.blit(s, (dx+23-sz, self.rect.centery-sz))
        pygame.draw.rect(surf, LGRAY, (dx, self.rect.y,
                                        self.rect.width, self.rect.height), 3)
        t = F_SM.render("EXIT", True, WHITE)
        surf.blit(t, (dx + self.rect.width//2 - t.get_width()//2,
                      self.rect.y - 24))


# ==================== LEVEL DATA ====================
def make_levels():
    levels = {}

    # Each level: dict with all needed data
    # Platforms are long to give the player room to navigate

    # ----- LEVEL 1  "First Shadow" -----
    levels[1] = dict(
        name="First Shadow",
        start=(60, 340),
        plats=[
            (0,400,320,25),(400,380,180,25),(660,360,160,25),
            (900,380,200,25),(1180,350,180,25),(1440,360,200,25),
            (1720,340,180,25),(1980,360,200,25),(2260,340,200,25),
            (2540,360,180,25),(2800,340,220,25),
            (0,530,3200,20),
        ],
        moving=[(580,360,100,18,[(580,360),(580,290)],1.3)],
        falling=[],
        spikes=[(320,400,2,'up'),(840,380,2,'up'),(1360,380,2,'up'),
                (1900,380,2,'up'),(2460,380,2,'up')],
        bounce=[],
        levers=[],doors=[],
        saws=[],lasers=[],
        cps=[(900,380),(1720,340)],
        goal=(2900,260),
    )

    # ----- LEVEL 2  "Moving Shadows" -----
    levels[2] = dict(
        name="Moving Shadows",
        start=(60, 340),
        plats=[
            (0,400,200,25),(1000,380,180,25),(1900,360,200,25),
            (2800,340,250,25),(0,530,3200,20),
        ],
        moving=[
            (250,380,110,18,[(250,380),(450,380)],2.0),
            (520,340,100,18,[(520,340),(520,260)],1.8),
            (680,380,110,18,[(680,380),(680,300)],2.2),
            (1240,360,110,18,[(1240,360),(1440,360)],2.5),
            (1560,300,100,18,[(1560,300),(1560,400)],2.0),
            (1700,360,110,18,[(1700,360),(1700,280)],2.4),
            (2160,340,110,18,[(2160,340),(2360,340)],2.8),
            (2440,280,100,18,[(2440,280),(2440,380)],2.2),
            (2560,340,100,18,[(2560,340),(2560,260)],2.0),
        ],
        falling=[],
        spikes=[(200,400,3,'up'),(1800,510,3,'up')],
        bounce=[],levers=[],doors=[],
        saws=[(700,290,18,[(700,290),(800,290)],2.5)],
        lasers=[],
        cps=[(1000,380),(1900,360)],
        goal=(2930,260),
    )

    # ----- LEVEL 3  "Blade Forest" -----
    levels[3] = dict(
        name="Blade Forest",
        start=(60, 360),
        plats=[
            (0,420,220,25),(340,400,140,25),(560,380,140,25),
            (780,360,140,25),(1000,380,140,25),(1220,360,140,25),
            (1440,340,140,25),(1700,360,160,25),(1960,340,160,25),
            (2220,360,160,25),(2500,340,200,25),(2780,320,220,25),
            (0,530,3200,20),
        ],
        moving=[],falling=[],
        spikes=[(220,420,2,'up'),(700,510,2,'up'),(1600,510,2,'up'),
                (2100,510,2,'up')],
        bounce=[],levers=[],doors=[],
        saws=[
            (420,390,20,[(340,390),(480,390)],2.5),
            (640,370,20,[(560,370),(700,370)],3.0),
            (860,350,20,[(780,350),(940,350)],2.8),
            (1080,370,20,[(1000,370),(1160,370)],3.2),
            (1300,350,20,[(1220,350),(1380,350)],3.0),
            (1520,330,20,[(1440,330),(1580,330)],3.5),
            (1780,350,20,[(1700,350),(1860,350)],3.0),
            (2040,330,20,[(1960,330),(2100,330)],3.5),
        ],
        lasers=[],
        cps=[(1000,380),(1700,360)],
        goal=(2880,240),
    )

    # ----- LEVEL 4  "Gate Keeper" -----
    levels[4] = dict(
        name="Gate Keeper",
        start=(60, 370),
        plats=[
            (0,430,200,25),(380,420,120,25),(600,400,120,25),
            (820,420,120,25),(1060,400,120,25),(1340,380,150,25),
            (1600,400,150,25),(1860,380,150,25),(2120,360,180,25),
            (2400,340,220,25),(2700,320,240,25),
            (0,530,3200,20),
        ],
        moving=[],falling=[],
        spikes=[(340,430,2,'up'),(740,510,2,'up'),(1240,510,2,'up')],
        bounce=[],
        levers=[
            (100,430,'DA'),(880,420,'DB'),(1700,400,'DC'),
        ],
        doors=[
            (300,340,28,90,'DA'),(780,330,28,90,'DB'),(1540,310,28,90,'DC'),
        ],
        saws=[],lasers=[],
        cps=[(820,420),(1600,400)],
        goal=(2820,240),
    )

    # ----- LEVEL 5  "Laser Grid" -----
    levels[5] = dict(
        name="Laser Grid",
        start=(60, 360),
        plats=[
            (0,420,200,25),(340,400,140,25),(580,380,140,25),
            (820,400,140,25),(1060,380,140,25),(1300,360,140,25),
            (1560,380,160,25),(1820,360,160,25),(2100,340,180,25),
            (2380,320,200,25),(2660,300,220,25),
            (0,530,3200,20),
        ],
        moving=[],falling=[],
        spikes=[(200,420,2,'up'),(720,510,2,'up'),(1200,510,2,'up')],
        bounce=[],levers=[],doors=[],saws=[],
        lasers=[
            (340,350,480,350,100),(580,330,720,330,80),
            (820,350,960,350,120),(1060,330,1200,330,90),
            (1300,310,1440,310,110),(1560,330,1700,330,85),
            (1820,310,1960,310,95),(2100,290,2240,290,105),
        ],
        cps=[(820,400),(1560,380)],
        goal=(2780,220),
    )

    # ----- LEVEL 6  "Bounce or Die" -----
    levels[6] = dict(
        name="Bounce or Die",
        start=(60, 380),
        plats=[
            (0,440,200,25),(0,530,3200,20),
            (460,440,80,25),(800,420,80,25),(1140,400,80,25),
            (1480,380,80,25),(1820,360,80,25),(2160,340,80,25),
            (2500,320,200,25),(2780,300,200,25),
        ],
        moving=[],falling=[],
        spikes=[(200,440,4,'up'),(560,510,3,'up'),(900,510,3,'up'),
                (1240,510,3,'up'),(1580,510,3,'up'),(1920,510,3,'up')],
        bounce=[
            (200,440,70,18),(540,440,70,18),(880,420,70,18),
            (1220,400,70,18),(1560,380,70,18),(1900,360,70,18),
            (2240,340,70,18),
        ],
        levers=[],doors=[],saws=[],lasers=[],
        cps=[(1140,400),(1820,360)],
        goal=(2880,220),
    )

    # ----- LEVEL 7  "The Fall" -----
    levels[7] = dict(
        name="The Fall",
        start=(60, 320),
        plats=[
            (0,380,180,25),(0,530,3200,20),
        ],
        moving=[],
        falling=[
            (230,355,120,18),(420,330,120,18),(610,305,120,18),
            (800,330,120,18),(990,305,120,18),(1180,280,120,18),
            (1370,255,120,18),(1560,280,120,18),(1750,255,120,18),
            (1940,230,120,18),(2130,255,120,18),(2320,230,120,18),
            (2510,205,120,18),(2700,230,120,18),
        ],
        spikes=[(0,510,10,'up')],
        bounce=[],levers=[],doors=[],saws=[],lasers=[],
        cps=[(990,305),(1750,255)],
        goal=(2820,150),
    )

    # ----- LEVEL 8  "Maze of Blades" -----
    levels[8] = dict(
        name="Maze of Blades",
        start=(60, 360),
        plats=[
            (0,420,200,25),(340,400,120,25),(560,380,120,25),
            (780,400,120,25),(1000,380,120,25),(1240,360,120,25),
            (1480,380,120,25),(1720,360,120,25),(1960,340,120,25),
            (2200,360,120,25),(2440,340,140,25),(2700,320,220,25),
            (0,530,3200,20),
        ],
        moving=[
            (460,380,80,18,[(460,380),(460,310)],2.2),
            (680,360,80,18,[(680,360),(680,290)],2.5),
            (1140,340,80,18,[(1140,340),(1140,270)],2.8),
            (1640,360,80,18,[(1640,360),(1640,290)],3.0),
        ],
        falling=[],
        spikes=[(200,420,2,'up'),(880,510,2,'up'),(2080,510,2,'up')],
        bounce=[],levers=[],doors=[],
        saws=[
            (400,390,18,[(340,390),(460,390)],3.0),
            (620,370,18,[(560,370),(680,370)],3.5),
            (840,390,18,[(780,390),(900,390)],3.2),
            (1060,370,18,[(1000,370),(1120,370)],3.8),
            (1300,350,18,[(1240,350),(1360,350)],3.5),
            (1540,370,18,[(1480,370),(1600,370)],4.0),
            (1780,350,18,[(1720,350),(1840,350)],3.8),
            (2020,330,18,[(1960,330),(2080,330)],4.0),
        ],
        lasers=[],
        cps=[(1000,380),(1720,360)],
        goal=(2820,240),
    )

    # ----- LEVEL 9  "Pendulum" -----
    levels[9] = dict(
        name="Pendulum",
        start=(60, 360),
        plats=[
            (0,420,200,25),(0,530,3200,20),
            (2700,300,260,25),
        ],
        moving=[
            (240,390,110,18,[(240,390),(400,390)],3.5),
            (460,360,100,18,[(460,360),(460,280)],3.0),
            (600,380,110,18,[(600,380),(760,380)],3.5),
            (820,350,100,18,[(820,350),(820,270)],3.2),
            (960,370,110,18,[(960,370),(1120,370)],4.0),
            (1180,340,100,18,[(1180,340),(1180,260)],3.5),
            (1320,360,110,18,[(1320,360),(1480,360)],4.0),
            (1540,320,100,18,[(1540,320),(1540,240)],3.8),
            (1680,350,110,18,[(1680,350),(1840,350)],4.5),
            (1900,310,100,18,[(1900,310),(1900,230)],4.0),
            (2040,330,110,18,[(2040,330),(2200,330)],4.5),
            (2260,290,100,18,[(2260,290),(2260,210)],4.2),
            (2400,320,110,18,[(2400,320),(2560,320)],5.0),
        ],
        falling=[],
        spikes=[(200,400,4,'up'),(800,510,3,'up'),(1500,510,3,'up')],
        bounce=[],levers=[],doors=[],
        saws=[(700,330,20,[(600,330),(760,330)],4.0),
              (1400,300,20,[(1320,300),(1480,300)],4.5)],
        lasers=[],
        cps=[(960,370),(1680,350)],
        goal=(2800,220),
    )

    # ----- LEVEL 10  "All Together" -----
    levels[10] = dict(
        name="All Together",
        start=(60, 360),
        plats=[
            (0,420,200,25),(600,400,120,25),(1100,380,120,25),
            (1700,360,120,25),(2200,340,120,25),(2700,320,260,25),
            (0,530,3200,20),
        ],
        moving=[
            (260,390,100,18,[(260,390),(440,390)],2.5),
            (780,370,100,18,[(780,370),(780,290)],2.8),
            (1280,350,100,18,[(1280,350),(1280,270)],3.0),
            (1880,330,100,18,[(1880,330),(2060,330)],3.5),
            (2380,310,100,18,[(2380,310),(2380,230)],3.2),
        ],
        falling=[
            (500,390,100,18),(1000,370,100,18),(1600,350,100,18),
        ],
        spikes=[(200,420,2,'up'),(700,510,2,'up'),(1200,510,2,'up'),
                (1800,510,2,'up')],
        bounce=[(1050,370,65,17)],
        levers=[(100,420,'D10'),(1750,360,'D10B')],
        doors=[(440,330,28,90,'D10'),(1640,270,28,90,'D10B')],
        saws=[
            (670,380,20,[(600,380),(720,380)],3.5),
            (1170,360,20,[(1100,360),(1220,360)],4.0),
            (2270,320,20,[(2200,320),(2320,320)],4.5),
        ],
        lasers=[
            (780,340,900,340,90),(1280,320,1400,320,80),
        ],
        cps=[(1100,380),(1700,360)],
        goal=(2870,240),
    )

    # ----- LEVELS 11-20  "The Descent" -----
    for i in range(11, 21):
        levels[i] = _auto_level(i)

    # ----- LEVELS 21-30  "The Abyss" -----
    for i in range(21, 31):
        levels[i] = _auto_level(i)

    # ----- LEVELS 31-40  "Nightmare" -----
    for i in range(31, 41):
        levels[i] = _auto_level(i)

    # ----- LEVELS 41-50  "Final Darkness" -----
    for i in range(41, 51):
        levels[i] = _auto_level(i)

    return levels


def _auto_level(n):
    random.seed(n * 211 + 73)
    diff  = min(1.0, (n - 1) / 49.0)
    names = ["Dark Corridor","Void Walk","Shadow Run","Edge of Nothing",
             "Nightmare Path","Abyss","Eternal Dark","The End Is Near",
             "No Way Back","Final Breath","Limbo Deep","Cursed Ground",
             "Silent Death","Black Horizon","Forgotten World"]
    name = names[(n-11) % len(names)] + f"  {n}"

    base_y   = 420
    plats    = [(0, 530, 4000, 20)]
    moving   = []
    falling  = []
    spikes   = []
    bounce   = []
    levers   = []
    doors    = []
    saws     = []
    lasers   = []
    cps      = []

    # Start platform
    plats.append((0, base_y, 200, 25))

    x = 240
    cy = base_y
    last_cp = 0
    segs = 12 + int(diff * 10)

    options = ['gap','moving','falling','saw','laser','bounce','lever','climb','combo']
    weights = [8, 10, 7, 12, 10, 5, 6, 8, 6]

    if n > 30:
        weights = [2, 8, 5, 18, 16, 4, 4, 6, 10]
    if n > 40:
        weights = [1, 6, 4, 20, 20, 3, 3, 5, 12]

    for seg in range(segs):
        # weighted random
        total = sum(weights)
        r = random.randint(0, total - 1)
        acc = 0
        stype = options[0]
        for o, w in zip(options, weights):
            acc += w
            if r < acc:
                stype = o
                break

        gap = random.randint(130, 210)
        pw  = random.randint(90, 160)
        dy  = random.randint(-50, 50)
        cy  = max(180, min(460, cy + dy))
        spd = 1.5 + diff * 3.5

        if stype == 'gap':
            plats.append((x + gap, cy, pw, 25))
            if random.random() < 0.5: spikes.append((x+gap-20, 510, 2, 'up'))
            x += gap + pw

        elif stype == 'moving':
            rng  = random.randint(90, 170)
            axis = random.choice(['h','v'])
            pts  = [(x+gap, cy), (x+gap+rng, cy)] if axis == 'h' \
                   else [(x+gap, cy), (x+gap, cy-rng)]
            moving.append((x+gap, cy, 100, 18, pts, spd))
            x += gap + 100 + random.randint(60, 120)

        elif stype == 'falling':
            for j in range(random.randint(3, 6)):
                falling.append((x+gap+j*140, cy-j*20, 110, 18))
            x += gap + 6*140

        elif stype == 'saw':
            plats.append((x+gap, cy, pw+50, 25))
            sr   = 18 + int(diff * 8)
            rng  = pw + 50
            saws.append((x+gap, cy-20, sr,
                         [(x+gap, cy-20),(x+gap+rng, cy-20)], spd))
            x += gap + pw + 50

        elif stype == 'laser':
            plats.append((x+gap, cy, pw, 25))
            period = max(28, int(90 - diff*60))
            ly = cy - 28
            lasers.append((x+gap, ly, x+gap+pw, ly, period))
            x += gap + pw

        elif stype == 'bounce':
            plats.append((x+gap-20, cy+70, 160, 25))
            bounce.append((x+gap, cy+70, 75, 16+int(diff*5)))
            plats.append((x+gap+220, cy, pw, 25))
            x += gap + 220 + pw

        elif stype == 'lever':
            pw2 = pw + 60
            lid = f'DL{n}_{seg}'
            plats.append((x+gap, cy, pw2, 25))
            doors.append((x+gap-12, cy-90, 26, 90, lid))
            levers.append((x+gap+pw2-30, cy, lid))
            x += gap + pw2 + random.randint(60, 100)

        elif stype == 'climb':
            steps = random.randint(3, 6)
            for j in range(steps):
                cx2 = x + gap + j*130
                cy2 = cy - j*55
                if random.random() < 0.6:
                    plats.append((cx2, cy2, 100, 22))
                else:
                    rng = 70
                    moving.append((cx2, cy2, 90, 18,
                                   [(cx2,cy2),(cx2,cy2-rng)],
                                   spd*0.8))
            x += gap + steps*130
            cy -= steps*50

        elif stype == 'combo':
            # saw + laser combined
            plats.append((x+gap, cy, pw, 25))
            sr  = 16 + int(diff*6)
            saws.append((x+gap, cy-20, sr,
                         [(x+gap, cy-20),(x+gap+pw, cy-20)], spd*1.2))
            period = max(25, int(75 - diff*50))
            lasers.append((x+gap, cy-50, x+gap+pw, cy-50, period))
            spikes.append((x+gap+10, cy, 2, 'up'))
            x += gap + pw

        # Checkpoint every ~500px
        if x - last_cp > 480:
            cps.append((x - 60, cy))
            last_cp = x

    goal_x = x + 100
    goal_y = cy - 80

    return dict(
        name=name, start=(60, base_y-90),
        plats=plats, moving=moving, falling=falling,
        spikes=spikes, bounce=bounce,
        levers=levers, doors=doors,
        saws=saws, lasers=lasers,
        cps=cps, goal=(goal_x, goal_y),
    )


# ==================== BUILD FROM DATA ====================
def build(data):
    plats   = [Platform(*p) for p in data['plats']]
    moving  = [MovingPlatform(*m) for m in data['moving']]
    falling = [FallingPlatform(*f) for f in data['falling']]
    spikes  = [Spike(*s) for s in data['spikes']]
    bounce  = [BouncePad(*b) for b in data['bounce']]
    levers  = [Lever(*lv) for lv in data['levers']]
    doors   = [Door(*d) for d in data['doors']]
    saws    = [Saw(*s) for s in data['saws']]
    lasers  = [Laser(*l) for l in data['lasers']]
    cps     = [Checkpoint(*c) for c in data['cps']]
    goal    = Goal(*data['goal'])
    return plats, moving, falling, spikes, bounce, \
           levers, doors, saws, lasers, cps, goal


# ==================== BACKGROUND ====================
def draw_bg(surf, cam, tick):
    surf.fill(DARK)
    # Far trees
    for i in range(0, SW + 250, 95):
        ox = int((i - cam * 0.12) % (SW + 250)) - 100
        h  = 155 + (i % 55)
        pygame.draw.rect(surf, (11,11,17), (ox+38, SH-h, 17, h))
        pygame.draw.ellipse(surf, (14,14,21), (ox, SH-h-75, 92, 82))
    # Mid trees
    for i in range(0, SW + 250, 130):
        ox = int((i - cam * 0.28) % (SW + 250)) - 100
        h  = 115 + (i % 45)
        pygame.draw.rect(surf, (17,17,24), (ox+48, SH-h, 20, h))
        pygame.draw.ellipse(surf, (21,21,30), (ox+5, SH-h-85, 110, 90))
    # Near stumps
    for i in range(0, SW + 150, 65):
        ox = int((i - cam * 0.48) % (SW + 150)) - 50
        pygame.draw.rect(surf, (24,24,33), (ox+22, SH-58, 14, 58))
    # Stars
    for i in range(25):
        sx = (i * 131 - int(cam * 0.04)) % SW
        sy = (i * 89) % (SH // 2 - 20)
        a  = int(abs(math.sin(tick * 0.02 + i)) * 180 + 40)
        s  = pygame.Surface((3,3), pygame.SRCALPHA)
        pygame.draw.circle(s, (255,255,255,a), (1,1), 1)
        surf.blit(s, (sx, sy))


# ==================== HUD ====================
def draw_hud(surf, level_num, level_name, deaths, secs):
    # Top bar
    bar = pygame.Surface((SW, 50), pygame.SRCALPHA)
    bar.fill((0,0,0,130))
    surf.blit(bar, (0,0))

    t1 = F_MD.render(f"Level  {level_num}", True, WHITE)
    t2 = F_SM.render(level_name, True, LGRAY)
    t3 = F_SM.render(f"Deaths: {deaths}", True, LGRAY)
    t4 = F_SM.render(f"{secs//60:02d}:{secs%60:02d}", True, GRAY)
    surf.blit(t1, (12, 6))
    surf.blit(t2, (12, 30))
    surf.blit(t3, (SW-130, 6))
    surf.blit(t4, (SW-130, 28))

    # Progress bar
    bw = 260
    bx = SW//2 - bw//2
    pygame.draw.rect(surf, DGRAY,  (bx, 8, bw, 10))
    pw = int(bw * (level_num-1) / 50)
    if pw > 0:
        pygame.draw.rect(surf, LGRAY, (bx, 8, pw, 10))
    pygame.draw.rect(surf, GRAY,  (bx, 8, bw, 10), 1)

    # Bottom hint
    bot = pygame.Surface((SW, 26), pygame.SRCALPHA)
    bot.fill((0,0,0,90))
    surf.blit(bot, (0, SH-26))
    hint = F_SM.render(
        "Arrow / WASD : Move    SPACE : Jump    E : Interact    R : Restart",
        True, GRAY)
    surf.blit(hint, (SW//2 - hint.get_width()//2, SH-22))


# ==================== SCREENS ====================
def screen_menu(surf, tick):
    draw_bg(surf, 0, tick)
    ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
    ov.fill((0,0,0,110))
    surf.blit(ov, (0,0))

    pulse = abs(math.sin(tick*0.035))
    c = int(200 + pulse*55)
    t = F_XL.render("BLACK BOY", True, (c,c,c))
    surf.blit(t, (SW//2 - t.get_width()//2, 100))

    sub = F_MD.render("A Puzzle Platformer", True, LGRAY)
    surf.blit(sub, (SW//2 - sub.get_width()//2, 195))

    lines = [
        ("ENTER", "Start Game"),
        ("ESC",   "Quit"),
    ]
    by = 290
    for key, act in lines:
        k = F_MD.render(f"[ {key} ]", True, WHITE)
        a = F_MD.render(act, True, LGRAY)
        surf.blit(k, (SW//2 - 140, by))
        surf.blit(a, (SW//2 - 10, by))
        by += 48

    # controls box
    box_x, box_y, box_w, box_h = SW//2-210, 400, 420, 100
    pygame.draw.rect(surf, DGRAY, (box_x, box_y, box_w, box_h))
    pygame.draw.rect(surf, GRAY,  (box_x, box_y, box_w, box_h), 1)
    ctrl = [
        "? ? / A D   Move",
        "SPACE / W    Jump",
        "E            Activate lever",
        "R            Restart level",
    ]
    for i, c_txt in enumerate(ctrl):
        t = F_SM.render(c_txt, True, LGRAY)
        surf.blit(t, (box_x+14, box_y+10+i*22))


def screen_complete(surf, tick, lvl, deaths, secs):
    draw_bg(surf, 0, tick)
    ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
    ov.fill((0,0,0,155))
    surf.blit(ov, (0,0))

    pulse = abs(math.sin(tick*0.04))
    c = int(190+pulse*65)
    t = F_LG.render(f"Level  {lvl}  Complete!", True, (c,c,c))
    surf.blit(t, (SW//2-t.get_width()//2, 150))

    info = [
        f"Time:    {secs//60:02d}:{secs%60:02d}",
        f"Deaths:  {deaths}",
    ]
    for i,s in enumerate(info):
        tx = F_MD.render(s, True, LGRAY)
        surf.blit(tx, (SW//2-tx.get_width()//2, 260+i*48))

    bot = F_MD.render("ENTER  Next Level     R  Retry", True, GRAY)
    surf.blit(bot, (SW//2-bot.get_width()//2, 420))


def screen_credits(surf, tick, deaths, total_secs):
    draw_bg(surf, 0, tick)
    ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
    ov.fill((0,0,0,170))
    surf.blit(ov, (0,0))

    pulse = abs(math.sin(tick*0.04))
    c = int(180+pulse*75)
    t = F_XL.render("You Made It.", True, (c,c,c))
    surf.blit(t, (SW//2-t.get_width()//2, 110))

    sub = F_LG.render("BLACK BOY", True, LGRAY)
    surf.blit(sub, (SW//2-sub.get_width()//2, 210))

    info = [
        f"All 50 Levels Cleared",
        f"Total Deaths : {deaths}",
        f"Total Time   : {total_secs//60:02d}:{total_secs%60:02d}",
    ]
    for i,s in enumerate(info):
        tx = F_MD.render(s, True, LGRAY)
        surf.blit(tx, (SW//2-tx.get_width()//2, 300+i*45))

    bot = F_MD.render("R  Play Again", True, GRAY)
    surf.blit(bot, (SW//2-bot.get_width()//2, 470))


# ==================== MAIN GAME ====================
class Game:
    def __init__(self):
        self.all_data   = make_levels()
        self.level_num  = 1
        self.deaths     = 0
        self.total_time = 0
        self.state      = 'menu'
        self.tick       = 0
        self.parts      = Particles()
        self._load(1)

    def _load(self, n):
        self.level_num = n
        data = self.all_data[n]
        self.level_name = data['name']
        self.start_pos  = data['start']
        (self.plats, self.moving, self.falling,
         self.spikes, self.bounce,
         self.levers, self.doors,
         self.saws, self.lasers,
         self.cps, self.goal) = build(data)
        self.player      = Player(*self.start_pos)
        self.cam         = 0.0
        self.last_cp     = self.start_pos
        self.level_time  = 0
        self.parts.clear()
        play('ambient', loops=-1)

    def _respawn(self):
        self.deaths += 1
        self.player = Player(*self.last_cp)

    def _all_plats(self):
        return self.plats + self.moving + self.falling

    def _update_cam(self):
        target = self.player.rect.centerx - SW // 3
        self.cam += (target - self.cam) * 0.09
        self.cam  = max(0.0, self.cam)

    def update(self):
        if self.state != 'playing': return
        self.tick       += 1
        self.level_time += 1
        self.total_time += 1

        # Objects
        for m in self.moving:  m.update()
        for f in self.falling: f.update(self.player)
        for d in self.doors:   d.update()
        for lv in self.levers: lv.update(self.player, self.parts, self.doors)
        for sw in self.saws:   sw.update()
        for lb in self.lasers: lb.update()
        for bp in self.bounce: bp.update(self.player, self.parts)
        self.goal.update(self.parts)

        # Player
        self.player.update(self._all_plats(), self.parts)

        # Kill checks
        if self.player.alive:
            for sp in self.spikes:
                if sp.kills(self.player): self.player.die(self.parts)
            for sw in self.saws:
                if sw.kills(self.player): self.player.die(self.parts)
            for lb in self.lasers:
                if lb.kills(self.player): self.player.die(self.parts)

        # Door blocking
        for d in self.doors:
            if not d.open and d.rect.colliderect(self.player.rect):
                if self.player.vx > 0: self.player.rect.right = d.rect.left
                else:                  self.player.rect.left  = d.rect.right

        # Checkpoints
        for cp in self.cps:
            if cp.check(self.player, self.parts):
                self.last_cp = (self.player.rect.x, self.player.rect.y)

        # Goal
        if self.player.rect.colliderect(self.goal.rect):
            play('win')
            stop('ambient')
            if self.level_num >= 50:
                self.state = 'credits'
            else:
                self.state = 'complete'

        # Respawn
        if not self.player.alive and self.player.death_timer <= 0:
            self._respawn()

        self.parts.update()
        self._update_cam()

    def draw(self):
        cam = int(self.cam)
        draw_bg(screen, cam, self.tick)

        for p  in self.plats:   p.draw(screen, cam)
        for m  in self.moving:  m.draw(screen, cam)
        for f  in self.falling: f.draw(screen, cam)
        for d  in self.doors:   d.draw(screen, cam)
        for bp in self.bounce:  bp.draw(screen, cam)
        for sp in self.spikes:  sp.draw(screen, cam)
        for lb in self.lasers:  lb.draw(screen, cam)
        for sw in self.saws:    sw.draw(screen, cam)
        for lv in self.levers:  lv.draw(screen, cam)
        for cp in self.cps:     cp.draw(screen, cam)

        self.goal.draw(screen, cam)
        self.parts.draw(screen, cam)
        self.player.draw(screen, cam, self.tick)

        draw_hud(screen, self.level_num, self.level_name,
                 self.deaths, self.level_time // FPS)

        # Death overlay
        if not self.player.alive:
            a   = max(0, min(190, int(190*(1 - self.player.death_timer/100))))
            ov  = pygame.Surface((SW, SH), pygame.SRCALPHA)
            ov.fill((0,0,0,a))
            screen.blit(ov, (0,0))
            if self.player.death_timer < 70:
                dt = F_LG.render("YOU DIED", True, RED)
                screen.blit(dt, (SW//2-dt.get_width()//2, SH//2-40))
                rt = F_SM.render("Respawning...", True, DRED)
                screen.blit(rt, (SW//2-rt.get_width()//2, SH//2+20))


def main():
    game  = Game()
    state = 'menu'
    game.state = 'menu'

    while True:
        game.tick += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop('ambient')
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:

                if game.state == 'menu':
                    if event.key == pygame.K_RETURN:
                        game._load(game.level_num)
                        game.state = 'playing'
                    elif event.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()

                elif game.state == 'playing':
                    if event.key == pygame.K_r:
                        game._load(game.level_num)
                        game.state = 'playing'
                    elif event.key == pygame.K_ESCAPE:
                        stop('ambient')
                        game.state = 'menu'

                elif game.state == 'complete':
                    if event.key == pygame.K_RETURN:
                        game._load(game.level_num + 1)
                        game.state = 'playing'
                    elif event.key == pygame.K_r:
                        game._load(game.level_num)
                        game.state = 'playing'

                elif game.state == 'credits':
                    if event.key == pygame.K_r:
                        game.deaths     = 0
                        game.total_time = 0
                        game._load(1)
                        game.state = 'playing'

        # Update & Draw
        if game.state == 'playing':
            game.update()
            game.draw()

        elif game.state == 'menu':
            screen_menu(screen, game.tick)

        elif game.state == 'complete':
            screen_complete(screen, game.tick, game.level_num,
                            game.deaths, game.level_time // FPS)

        elif game.state == 'credits':
            screen_credits(screen, game.tick,
                           game.deaths, game.total_time // FPS)

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
