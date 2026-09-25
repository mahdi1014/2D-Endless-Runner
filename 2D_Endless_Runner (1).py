"""
2D Endless Runner - Computer Graphics Sessional Project
Python + PyOpenGL + GLUT

Reference implementation for learning/debugging.
Read and understand the code before adapting it for submission.

CG techniques demonstrated:
1. Line & Shape Drawing
2. 2D Transformations
3. Color Fill
4. Line Clipping
5. Bezier Curve

Controls:
SPACE / UP       Jump
DOWN             Duck
P                 Pause
R                Restart
ESC              Exit
"""

from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import random
import math
import sys

WIDTH, HEIGHT = 1100, 650
GROUND_Y = 115
PLAYER_X = 170

game_started = False
paused = False
game_over = False

player_y = GROUND_Y
player_vy = 0.0
gravity = -0.85
jump_power = 15.5

ducking = False
score = 0
high_score = 0
speed = 7.0
frame_count = 0

obstacles = []
clouds = []
particles = []

# ---------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------

def set_color(c):
    glColor3f(c[0], c[1], c[2])


def draw_rect(x, y, w, h, color, fill=True):
    set_color(color)
    glBegin(GL_QUADS if fill else GL_LINE_LOOP)
    glVertex2f(x, y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x, y + h)
    glEnd()


def draw_circle(cx, cy, r, color, fill=True, segments=40):
    set_color(color)
    glBegin(GL_TRIANGLE_FAN if fill else GL_LINE_LOOP)
    if fill:
        glVertex2f(cx, cy)

    count = segments if fill else segments + 1
    for i in range(count):
        a = 2 * math.pi * i / segments
        glVertex2f(cx + r * math.cos(a), cy + r * math.sin(a))
    glEnd()


def draw_triangle(cx, cy, w, h, color, rotation=0):
    points = [
        (cx, cy + h / 2),
        (cx - w / 2, cy - h / 2),
        (cx + w / 2, cy - h / 2)
    ]

    rotated = []
    r = math.radians(rotation)
    c, s = math.cos(r), math.sin(r)

    for x, y in points:
        dx, dy = x - cx, y - cy
        rotated.append((
            cx + dx * c - dy * s,
            cy + dx * s + dy * c
        ))

    set_color(color)
    glBegin(GL_TRIANGLES)
    for p in rotated:
        glVertex2f(*p)
    glEnd()


def draw_text(x, y, text, color=(0.1, 0.1, 0.1),
              font=GLUT_BITMAP_9_BY_15):
    set_color(color)
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))


# ---------------------------------------------------------------------
# Line clipping: Cohen-Sutherland
# ---------------------------------------------------------------------

LEFT, RIGHT, BOTTOM, TOP = 1, 2, 4, 8


def clip_code(x, y):
    # কী করছে: viewport boundary-এর বাইরে থাকা point-এর region code তৈরি করে।
    # কেন লাগছে: line clipping algorithm-এর জন্য।
    # real world-এ এটা কোথায় দেখা যায়: graphics rendering pipeline-এ।

    code = 0

    if x < 0:
        code |= LEFT
    elif x > WIDTH:
        code |= RIGHT

    if y < 0:
        code |= BOTTOM
    elif y > HEIGHT:
        code |= TOP

    return code


def clip_line(x1, y1, x2, y2):
    # কী করছে: Cohen-Sutherland algorithm দিয়ে line-এর visible অংশ বের করে।
    # কেন লাগছে: screen boundary-এর বাইরে থাকা line বাদ দিতে।
    # real world-এ এটা কোথায় দেখা যায়: viewport clipping-এ।

    c1 = clip_code(x1, y1)
    c2 = clip_code(x2, y2)

    while True:
        if not (c1 | c2):
            return x1, y1, x2, y2

        if c1 & c2:
            return None

        out = c1 if c1 else c2

        if out & TOP:
            if y2 == y1:
                return None
            x = x1 + (x2 - x1) * (HEIGHT - y1) / (y2 - y1)
            y = HEIGHT
        elif out & BOTTOM:
            if y2 == y1:
                return None
            x = x1 + (x2 - x1) * (-y1) / (y2 - y1)
            y = 0
        elif out & RIGHT:
            if x2 == x1:
                return None
            y = y1 + (y2 - y1) * (WIDTH - x1) / (x2 - x1)
            x = WIDTH
        else:
            if x2 == x1:
                return None
            y = y1 + (y2 - y1) * (-x1) / (x2 - x1)
            x = 0

        if out == c1:
            x1, y1 = x, y
            c1 = clip_code(x1, y1)
        else:
            x2, y2 = x, y
            c2 = clip_code(x2, y2)


# ---------------------------------------------------------------------
# Bezier curve
# ---------------------------------------------------------------------

def bezier_point(points, t):
    # কী করছে: 4 control point ব্যবহার করে cubic Bezier point বের করে।
    # কেন লাগছে: curved clouds/decoration/paths তৈরি করতে।
    # real world-এ এটা কোথায় দেখা যায়: animation paths এবং vector graphics-এ।

    p0, p1, p2, p3 = points
    u = 1.0 - t

    x = (
        u**3 * p0[0]
        + 3 * u**2 * t * p1[0]
        + 3 * u * t**2 * p2[0]
        + t**3 * p3[0]
    )

    y = (
        u**3 * p0[1]
        + 3 * u**2 * t * p1[1]
        + 3 * u * t**2 * p2[1]
        + t**3 * p3[1]
    )

    return x, y


def draw_bezier(points, color, width=2):
    set_color(color)
    glLineWidth(width)

    glBegin(GL_LINE_STRIP)
    for i in range(101):
        x, y = bezier_point(points, i / 100.0)
        glVertex2f(x, y)
    glEnd()

    glLineWidth(1)


# ---------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------

def player_box():
    if ducking:
        return PLAYER_X - 28, player_y, 56, 38

    return PLAYER_X - 23, player_y, 46, 76


def draw_player():
    # কী করছে: player character-এর body parts shape দিয়ে আঁকে।
    # কেন লাগছে: game character visualisation-এর জন্য।
    # real world-এ এটা কোথায় দেখা যায়: 2D games এবং animation-এ।

    x = PLAYER_X

    if ducking:
        body_y = player_y + 12
        body_h = 28
    else:
        body_y = player_y + 25
        body_h = 45

    # Body
    draw_rect(x - 20, body_y, 40, body_h,
              (0.12, 0.42, 0.90), True)

    # Head
    draw_circle(x, body_y + body_h + 17, 17,
                (1.0, 0.78, 0.55), True)

    # Eye
    draw_circle(x + 6, body_y + body_h + 21, 3,
                (0.05, 0.05, 0.05), True)

    # Legs
    if not ducking:
        # 2D transformation: legs are drawn as moving/offset parts.
        draw_rect(x - 18, player_y, 10, 25,
                  (0.08, 0.08, 0.12), True)
        draw_rect(x + 8, player_y, 10, 25,
                  (0.08, 0.08, 0.12), True)
    else:
        draw_rect(x - 24, player_y, 16, 10,
                  (0.08, 0.08, 0.12), True)
        draw_rect(x + 8, player_y, 16, 10,
                  (0.08, 0.08, 0.12), True)


# ---------------------------------------------------------------------
# Obstacles
# ---------------------------------------------------------------------

def spawn_obstacle():
    kind = random.choice(["cactus", "rock", "double_cactus"])

    obj = {
        "x": WIDTH + 30,
        "kind": kind,
    }

    if kind == "cactus":
        obj["w"] = 35
        obj["h"] = random.randint(50, 75)
    elif kind == "rock":
        obj["w"] = 55
        obj["h"] = 35
    else:
        obj["w"] = 65
        obj["h"] = random.randint(50, 75)

    obstacles.append(obj)


def draw_cactus(x, y, w, h):
    set_color((0.08, 0.50, 0.18))

    # Main stem
    draw_rect(x + w * 0.35, y, w * 0.30, h, 
              (0.08, 0.50, 0.18), True)

    # Left arm
    draw_rect(x, y + h * 0.40, w * 0.38, h * 0.18,
              (0.08, 0.50, 0.18), True)
    draw_rect(x + w * 0.10, y + h * 0.40,
              w * 0.18, h * 0.25,
              (0.08, 0.50, 0.18), True)

    # Right arm
    draw_rect(x + w * 0.62, y + h * 0.55,
              w * 0.38, h * 0.18,
              (0.08, 0.50, 0.18), True)
    draw_rect(x + w * 0.72, y + h * 0.55,
              w * 0.18, h * 0.25,
              (0.08, 0.50, 0.18), True)


def draw_obstacle(obj):
    x = obj["x"]

    if obj["kind"] == "cactus":
        draw_cactus(x, GROUND_Y, obj["w"], obj["h"])

    elif obj["kind"] == "double_cactus":
        draw_cactus(x, GROUND_Y, obj["w"], obj["h"])
        draw_cactus(x + 30, GROUND_Y, obj["w"] * 0.7,
                    obj["h"] * 0.75)

    else:
        # Rock
        draw_triangle(x + obj["w"] / 2,
                      GROUND_Y + obj["h"] / 2,
                      obj["w"], obj["h"],
                      (0.30, 0.32, 0.35),
                      rotation=0)


def obstacle_box(obj):
    return (
        obj["x"],
        GROUND_Y,
        obj["w"] + (30 if obj["kind"] == "double_cactus" else 0),
        obj["h"]
    )


def rectangles_collide(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b

    return (
        ax < bx + bw and
        ax + aw > bx and
        ay < by + bh and
        ay + ah > by
    )


# ---------------------------------------------------------------------
# Clouds
# ---------------------------------------------------------------------

def create_cloud():
    y = random.randint(390, 560)
    x = WIDTH + random.randint(30, 150)

    clouds.append({
        "x": x,
        "y": y,
        "speed": random.uniform(1.0, 2.0)
    })


def draw_cloud(cloud):
    x = cloud["x"]
    y = cloud["y"]

    # Bezier curve is used for a soft curved cloud bottom.
    points = [
        (x - 60, y),
        (x - 35, y - 35),
        (x + 35, y - 35),
        (x + 60, y)
    ]

    draw_bezier(points, (0.75, 0.80, 0.88), 2)

    draw_circle(x - 30, y + 10, 23,
                (0.88, 0.91, 0.96), True)
    draw_circle(x, y + 20, 30,
                (0.92, 0.94, 0.98), True)
    draw_circle(x + 32, y + 10, 22,
                (0.88, 0.91, 0.96), True)


# ---------------------------------------------------------------------
# Ground / background
# ---------------------------------------------------------------------

def draw_background():
    # Sky
    draw_rect(0, 0, WIDTH, HEIGHT,
              (0.78, 0.90, 1.0), True)

    # Sun
    draw_circle(WIDTH - 120, HEIGHT - 100, 48,
                (1.0, 0.80, 0.20), True)

    # Clouds
    for cloud in clouds:
        draw_cloud(cloud)

    # Distant hills using triangles
    for i in range(-1, 8):
        draw_triangle(
            i * 180 + 70,
            GROUND_Y + 90,
            240,
            180,
            (0.56, 0.74, 0.58)
        )

    # Ground
    draw_rect(0, 0, WIDTH, GROUND_Y,
              (0.78, 0.67, 0.45), True)

    # Ground line
    set_color((0.20, 0.20, 0.20))
    glLineWidth(4)

    # Demonstrates clipping because the line is deliberately longer
    # than the viewport.
    clipped = clip_line(-200, GROUND_Y, WIDTH + 200, GROUND_Y)

    if clipped:
        x1, y1, x2, y2 = clipped
        glBegin(GL_LINES)
        glVertex2f(x1, y1)
        glVertex2f(x2, y2)
        glEnd()

    glLineWidth(1)

    # Moving ground marks
    mark_offset = (frame_count * speed) % 90

    for x in range(-100, WIDTH + 100, 90):
        draw_rect(x - mark_offset,
                  GROUND_Y - 18,
                  45, 5,
                  (0.45, 0.35, 0.22), True)


# ---------------------------------------------------------------------
# Particles
# ---------------------------------------------------------------------

def add_dust():
    for _ in range(2):
        particles.append({
            "x": PLAYER_X - 18,
            "y": player_y + 5,
            "vx": random.uniform(-2.5, -0.5),
            "vy": random.uniform(0.5, 2.0),
            "life": random.randint(15, 30)
        })


def update_particles():
    for p in particles[:]:
        p["x"] += p["vx"]
        p["y"] += p["vy"]
        p["vy"] -= 0.08
        p["life"] -= 1

        if p["life"] <= 0:
            particles.remove(p)


def draw_particles():
    for p in particles:
        alpha = max(0.0, p["life"] / 30.0)
        set_color((0.45 * alpha, 0.38 * alpha, 0.28 * alpha))
        draw_circle(p["x"], p["y"], 3, 
                    (0.45 * alpha, 0.38 * alpha, 0.28 * alpha), True)


# ---------------------------------------------------------------------
# Game logic
# ---------------------------------------------------------------------

def reset_game():
    global game_started, paused, game_over
    global player_y, player_vy, ducking
    global score, speed, frame_count

    game_started = True
    paused = False
    game_over = False

    player_y = GROUND_Y
    player_vy = 0
    ducking = False

    score = 0
    speed = 7.0
    frame_count = 0

    obstacles.clear()
    particles.clear()

    for cloud in clouds:
        cloud["x"] = random.randint(0, WIDTH)

    spawn_obstacle()


def jump():
    global player_vy

    if game_over:
        reset_game()
        return

    if player_y <= GROUND_Y + 1:
        player_vy = jump_power


def update_game():
    global player_y, player_vy
    global score, speed, frame_count
    global game_over, high_score

    if not game_started or paused or game_over:
        return

    frame_count += 1

    # 2D transformation: vertical translation through physics.
    player_vy += gravity
    player_y += player_vy

    if player_y <= GROUND_Y:
        player_y = GROUND_Y
        player_vy = 0

    if frame_count % 8 == 0:
        add_dust()

    # Move obstacles
    for obj in obstacles:
        obj["x"] -= speed

    # Remove old obstacles
    obstacles[:] = [
        obj for obj in obstacles
        if obj["x"] > -150
    ]

    # Spawn logic
    if not obstacles or obstacles[-1]["x"] < WIDTH - random.randint(330, 500):
        spawn_obstacle()

    # Score and difficulty
    score += 1

    if score % 500 == 0:
        speed += 0.6

    # Collision
    pbox = player_box()

    for obj in obstacles:
        if rectangles_collide(pbox, obstacle_box(obj)):
            game_over = True
            high_score = max(high_score, score)
            return

    # Clouds move
    for cloud in clouds:
        cloud["x"] -= cloud["speed"]

        if cloud["x"] < -150:
            cloud["x"] = WIDTH + random.randint(30, 150)
            cloud["y"] = random.randint(390, 560)

    update_particles()


def timer(value):
    update_game()
    glutPostRedisplay()
    glutTimerFunc(16, timer, 0)


# ---------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------

def draw_ui():
    draw_text(25, HEIGHT - 35,
              f"SCORE: {score}",
              (0.05, 0.08, 0.12),
              GLUT_BITMAP_HELVETICA_18)

    draw_text(WIDTH - 180, HEIGHT - 35,
              f"BEST: {high_score}",
              (0.05, 0.08, 0.12),
              GLUT_BITMAP_HELVETICA_18)

    draw_text(25, 25,
              "SPACE/UP: Jump   DOWN: Duck   P: Pause   R: Restart   ESC: Exit",
              (0.12, 0.12, 0.12))

    if not game_started:
        draw_rect(WIDTH / 2 - 230, HEIGHT / 2 - 90,
                  460, 180,
                  (1.0, 1.0, 1.0), True)

        draw_text(WIDTH / 2 - 135, HEIGHT / 2 + 35,
                  "2D ENDLESS RUNNER",
                  (0.08, 0.15, 0.30),
                  GLUT_BITMAP_HELVETICA_18)

        draw_text(WIDTH / 2 - 105, HEIGHT / 2 - 5,
                  "Press SPACE to Start",
                  (0.10, 0.10, 0.10))

        draw_text(WIDTH / 2 - 110, HEIGHT / 2 - 35,
                  "Avoid the obstacles!",
                  (0.10, 0.10, 0.10))

    elif paused:
        draw_rect(WIDTH / 2 - 150, HEIGHT / 2 - 55,
                  300, 110,
                  (1.0, 1.0, 1.0), True)

        draw_text(WIDTH / 2 - 45, HEIGHT / 2 + 10,
                  "PAUSED",
                  (0.10, 0.15, 0.25),
                  GLUT_BITMAP_HELVETICA_18)

        draw_text(WIDTH / 2 - 80, HEIGHT / 2 - 20,
                  "Press P to continue",
                  (0.10, 0.10, 0.10))

    elif game_over:
        draw_rect(WIDTH / 2 - 230, HEIGHT / 2 - 100,
                  460, 200,
                  (1.0, 1.0, 1.0), True)

        draw_text(WIDTH / 2 - 85, HEIGHT / 2 + 50,
                  "GAME OVER",
                  (0.80, 0.10, 0.10),
                  GLUT_BITMAP_HELVETICA_18)

        draw_text(WIDTH / 2 - 80, HEIGHT / 2 + 15,
                  f"Score: {score}",
                  (0.10, 0.10, 0.10))

        draw_text(WIDTH / 2 - 110, HEIGHT / 2 - 25,
                  "Press R to Restart",
                  (0.10, 0.10, 0.10))

        draw_text(WIDTH / 2 - 125, HEIGHT / 2 - 55,
                  "Press ESC to Exit",
                  (0.10, 0.10, 0.10))


# ---------------------------------------------------------------------
# GLUT callbacks
# ---------------------------------------------------------------------

def display():
    glClear(GL_COLOR_BUFFER_BIT)
    glLoadIdentity()

    draw_background()
    draw_particles()

    for obj in obstacles:
        draw_obstacle(obj)

    draw_player()
    draw_ui()

    glutSwapBuffers()


def reshape(w, h):
    global WIDTH, HEIGHT

    WIDTH = max(700, w)
    HEIGHT = max(450, h)

    glViewport(0, 0, WIDTH, HEIGHT)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, WIDTH, 0, HEIGHT)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()


def keyboard(key, x, y):
    global paused, game_started, ducking

    key = key.decode("utf-8").lower()

    if key == "\x1b":
        sys.exit(0)

    if key == " ":
        if not game_started:
            reset_game()
        else:
            jump()

    elif key == "p":
        if game_started and not game_over:
            paused = not paused

    elif key == "r":
        reset_game()

    elif key == "w":
        jump()


def special_keyboard(key, x, y):
    global ducking

    if key == GLUT_KEY_UP:
        jump()

    elif key == GLUT_KEY_DOWN:
        ducking = True


def special_up(key, x, y):
    global ducking

    if key == GLUT_KEY_DOWN:
        ducking = False


# ---------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------

def init():
    # কী করছে: OpenGL-এর 2D projection এবং rendering settings সেট করে।
    # কেন লাগছে: 2D game scene correctly display করার জন্য।
    # real world-এ এটা কোথায় দেখা যায়: OpenGL-based 2D games-এ।

    glClearColor(0.78, 0.90, 1.0, 1.0)

    glDisable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, WIDTH, 0, HEIGHT)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()


def create_initial_clouds():
    for _ in range(7):
        clouds.append({
            "x": random.randint(0, WIDTH),
            "y": random.randint(390, 560),
            "speed": random.uniform(0.7, 1.8)
        })


def main():
    random.seed()

    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB)
    glutInitWindowSize(WIDTH, HEIGHT)
    glutInitWindowPosition(80, 40)

    glutCreateWindow(
        b"2D Endless Runner - Computer Graphics Sessional"
    )

    init()
    create_initial_clouds()

    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboard)
    glutSpecialFunc(special_keyboard)
    glutSpecialUpFunc(special_up)

    glutTimerFunc(16, timer, 0)

    glutMainLoop()


if __name__ == "__main__":
    main()
