import json
import os
import re
import sys

VERBOSE = False
LL_RATIO = False

re_commit = re.compile("commit (.*)")
re_date = re.compile("Date:   (.*)")
re_rustc = re.compile("rustc: .*/([\w\-_\.]*)")
re_time = re.compile("( *)time: ([0-9\.]*)\s*(.*)")


def process(label, arg, n):
    in_files = []
    for i in range(0, n):
        in_name = os.path.join('raw', '%s--%s--%s.log'%(label, arg, i))
        in_files.append(open(in_name))

    out_name = os.path.join('processed', '%s--%s.json'%(label, arg))
    if VERBOSE:
        print "input:", in_files
        print "output:", out_name

    with open(out_name, 'w') as out_file:
        process_files(in_files, out_file)

    for f in in_files:
        f.close()


def process_files(in_files, out_file):
    data = {}
    data['header'] = mk_header(in_files[0])
    times = map(lambda f: mk_times(f), in_files)
    data['times'] = map(post_process_times, merge_times(times))

    json.dump(data, out_file, indent=4)



def mk_header(in_file):
    commit_line = in_file.readline()

    # skip merge and author lines
    author_line = in_file.readline()
    if author_line.startswith('Merge'):
        in_file.readline()
    date_line = in_file.readline()

    header = {}
    header['commit'] = re_commit.match(commit_line).group(1)
    header['date'] = re_date.match(date_line).group(1)

    return header


def mk_times(in_file):
    all_times = []
    # The last mentioned crate being compiled.
    last_file = None
    cur_times = None
    for line in in_file:
        time_match = re_time.match(line)
        if time_match:
            assert(last_file)
            if not cur_times:
                cur_times = {}
                cur_times['crate'] = last_file
                cur_times['times'] = []
            indent = time_match.group(1)
            time = time_match.group(2)
            label = time_match.group(3)
            # TODO do something with 'sub-times'
            if not indent:
                cur_times['times'].append((label, float(time)))
        elif cur_times:
            all_times.append(cur_times)
            cur_times = None
            last_file = None

        rustc_match = re_rustc.match(line)
        if rustc_match:
            last_file = rustc_match.group(1)

    return all_times

# Takes an array of times and returns a single object of times,
def merge_times(times):
    for t in times:
        t.sort(key=lambda t: t['crate'])
        if len(t) != len(times[0]):
            print "Inconsistent data"
            return

    crates = []
    for ci in range(len(times[0])):
        c = times[0][ci]
        cur = {}
        cur['crate'] = c['crate']
        cur['times'] = []
        for i in range(len(c['times'])):
            cur['times'].append((c['times'][i][0], average(times, lambda t: t[ci]['times'][i][1])))
        crates.append(cur)

    return crates

def average(times, f):
    if len(times) <= 4:
        total = sum(map(f, times))
        return total/len(times)

    # Exclude the highest and lowest values.
    times = map(f, times)
    times.sort()
    return sum(times[1:-1])/(len(times)-2)

def post_process_times(times):
    total = 0
    llvm = 0
    for (l, t) in times['times']:
        total += t
        if LL_RATIO and l in ['translation', 'LLVM passes', 'linking']:
            llvm += t

    new_times = {}

    for (l, t) in times['times']:
        time = {
            'time': t,
            'percent': (t/total)*100
        }
        if LL_RATIO:
            time['ratio_llvm'] = (t/llvm)

        new_times[l] = time

    times['times'] = new_times
    times['total'] = total
    return times



if len(sys.argv) <= 3:
    print "Requires label, filename of log, and number of logs as arguments"
    exit(1)

process(sys.argv[1], sys.argv[2], int(sys.argv[3]))
