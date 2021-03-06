#!/usr/bin/env python3

"""
Created by Tennyson T Bardwell, tennysontaylorbardwell@gmail.com, on 2018-10-07

Copyright 2018 Tennyson T Bardwell

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import curses, datetime, threading, time, csv, argparse, textwrap


SECOND = datetime.timedelta(seconds=1)


exit_flag = False
wait_for_continue = False
stdscr = None
subject_name = None


def setup_curses():
    global stdscr
    stdscr = curses.initscr()
    stdscr.clear()
    stdscr.refresh()


def format(delta):
    return '{}.{}'.format(delta.seconds, delta.microseconds)


class Run:
    def __init__(self,
                 run_name,
                 prompt,
                 time_looking_at_images=None,
                 time_after_looking_at_an_image=None,
                 min_time_looking_at_an_image=None):

        if time_looking_at_images is None and \
           time_after_looking_at_an_image is None:
            raise ValueError('Run "{}" will never end'.format(run_name))

        self.run_name = run_name
        self.prompt = prompt
        self.time_looking_at_images = time_looking_at_images
        self.time_after_looking_at_an_image = time_after_looking_at_an_image
        self.min_time_looking_at_an_image = min_time_looking_at_an_image


    def append_log(self, action, time_):
        delta = time_ - self.last_log_timestamp
        self.last_log_timestamp = time_
        self.log.append([action,
                    format(delta),
                    format(self.time_spent['away']),
                    format(self.time_spent['left']),
                    format(self.time_spent['right']),])

    def start(self):
        self.time_spent = {
            'away': datetime.timedelta(),
            'left': datetime.timedelta(),
            'right': datetime.timedelta()
        }
        self.focus = 'away'  # left, right, awway
        self.last_change = datetime.datetime.now()
        self.first_look_at_image = None
        self.last_log_timestamp = self.last_change
        self.log = [['focus', 'timestamp', 'time since last action',
                     'total away time', 'total left time', 'total right time']]
        self.append_log(self.focus, self.last_change)

    def show_prompt(self, stdscr, msg=''):
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        stdscr.addstr(height // 2 - 3, 0, self.run_name)
        stdscr.addstr(height // 2 - 2, 0, '=' * len(self.run_name))
        stdscr.addstr(height // 2 - 0, 0, '(press SPACE to continue)')
        for i,line in enumerate(self.prompt.split('\n')):
            stdscr.addstr(height // 2 + 2 + i, 0, line)
        stdscr.addstr(height // 2 + 4 + len(self.prompt.split('\n')), 0, msg)
        stdscr.refresh()
    
    def display(self, stdscr):
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        stdscr.addstr(height // 2, 0, 'Current focus: ' + self.focus)
        for i,(k,v) in enumerate(self.time_spent.items()):
            stdscr.addstr(height // 2 + i + 1, 0,
                        'Time spent {}: {} seconds'.format(k, format(v)))
        stdscr.refresh()

    def update(self, new_focus=None):
        current_time = datetime.datetime.now()
        delta = (current_time - self.last_change)
        self.time_spent[self.focus] += delta
        self.last_change = current_time

        if new_focus is None:
            new_focus = self.focus
        elif new_focus != self.focus:
            self.append_log(new_focus, current_time)
            # keep track of when they first look at the image
            if self.first_look_at_image is None:
                self.first_look_at_image = current_time

        self.focus = new_focus

        image_time = self.time_spent['left'] + self.time_spent['right'] 
        if self.first_look_at_image is None:
            look_time = datetime.timedelta()
        else:
            look_time = current_time - self.first_look_at_image

        save = lambda: self.append_log('finish', datetime.datetime.now())
        if self.time_looking_at_images and \
           image_time > self.time_looking_at_images:
            save()
            return 'success'

        elif self.time_after_looking_at_an_image and \
           look_time > self.time_after_looking_at_an_image:
            if self.min_time_looking_at_an_image is not None and \
               image_time < self.min_time_looking_at_an_image:
                save()
                return 'failed'
            else:
                save()
                return 'success'
        else:
            return 'running'


def receive_keys(callback):
    global exit_flag
    while True:
        k = stdscr.getch()
        if k == ord('q'):  # q key and esc key
            print("Saw an exit key, quitting the program without saving")
            exit_flag = True
            exit()
        elif k == curses.KEY_UP:
            callback('away')
        elif k == curses.KEY_RIGHT:
            callback('right')
        elif k == curses.KEY_LEFT:
            callback('left')
        elif k == ord(' '):
            callback('continue')

def get_runs():
    '''In this function a list of 'runs' is created. Each run may either be
    a Trial or a Test Run. Each run is created like this:

    yield Run(
        run_name= ,
        prompt= ,
        time_looking_at_images=TIME_LOOKING_AT_IMAGES * SECOND,
        time_after_looking_at_an_image=TIME_AFTER_LOOKING_AT_AN_IMAGE * SECOND,
        min_time_looking_at_an_image=MIN_TIME_LOOKING_AT_AN_IMAGE * SECOND)

    Where the variables are such:

    PHASE_NAME: The name of the run, shown to user before the run starts
        and in filename
    PROMPT: what the user should be shown before the run starts
    TIME_LOOKING_AT_IMAGES: the maximum time the child should look at the left
        image and right image (excluding time looking away)
    TIME_AFTER_LOOKING_AT_AN_IMAGE: the maximum time the run can run after
        the child has looked at an image
    MIN_TIME_LOOKING_AT_AN_IMAGE: the minimum time the child must have spent
        looking at images (sum of left and right) by the end of the run, else
        the run is failed

    '''
    PROMPT = textwrap.dedent('''\
        A child will be presented with two images

        Press the LEFT ARROW KEY when the child looks at the LEFT IMAGE

        Press the RIGHT ARROW KEY when the child looks at the RIGHT IMAGE

        Press the UP ARROW KEY when the child looks AWAY from both images.\
        ''')

    yield Run(
        run_name='Familiarization 1',
        prompt=PROMPT,
        time_looking_at_images=20 * SECOND,
        time_after_looking_at_an_image=None,
        min_time_looking_at_an_image=None)
    yield Run(
        run_name='Test 1a',
        prompt=PROMPT,
        time_looking_at_images=None,
        time_after_looking_at_an_image=20 * SECOND,
        min_time_looking_at_an_image=SECOND)
    yield Run(
        run_name='Test 1b',
        prompt=PROMPT,
        time_looking_at_images=None,
        time_after_looking_at_an_image=20 * SECOND,
        min_time_looking_at_an_image=SECOND)
    yield Run(
        run_name='Familiarization 2',
        prompt=PROMPT,
        time_looking_at_images=20 * SECOND,
        time_after_looking_at_an_image=None,
        min_time_looking_at_an_image=None)
    yield Run(
        run_name='Test 2a',
        prompt=PROMPT,
        time_looking_at_images=None,
        time_after_looking_at_an_image=20 * SECOND,
        min_time_looking_at_an_image=SECOND)
    yield Run(
        run_name='Test 2b',
        prompt=PROMPT,
        time_looking_at_images=None,
        time_after_looking_at_an_image=20 * SECOND,
        min_time_looking_at_an_image=SECOND)

def main(stdscr_):
    global stdscr, exit_flag, wait_for_continue
    stdscr = stdscr_
    setup_curses()

    current_run = None
    def handle_key(key):
        global wait_for_continue
        if current_run is not None and key in {'away', 'right', 'left'}:
            current_run.update(new_focus=key)
        elif key == 'continue':
            wait_for_continue = False

    thread = threading.Thread(target=receive_keys, args=[handle_key])
    thread.daemon = True
    thread.start()

    for run in get_runs():
        res = None
        while res is None or res == 'failed':
            global wait_for_continue

            wait_for_continue = True
            if res == 'failed':
                run.show_prompt(stdscr,
                        msg='THE PREVIOUS RUN FAILED. TRYING AGAIN.')
            else:
                run.show_prompt(stdscr)
            while wait_for_continue:
                if exit_flag:
                    exit()

            run.start()
            current_run = run
            while True:
                if exit_flag:
                    exit()

                res = run.update()
                run.display(stdscr_)

                if res in {'success', 'failed'}:
                    if res == 'success':
                        name = "{}_{}.csv".format(subject_name,
                                                  run.run_name)
                    else:
                        name = '{}_{}_failed_{}.csv'.format(
                            subject_name,
                            run.run_name,
                            datetime.datetime.now())
                    with open(name, "w") as f:
                        writer = csv.writer(f)
                        writer.writerows(run.log)
                    break

                time.sleep(0.05)


if __name__ == '__main__':
    subject_name = input('Subject Name: ')
    curses.wrapper(main)
