with open(r'timetable_generator/solver.py') as f:
    content = f.read()
keys = set()
for line in content.splitlines():
    if 'self.w[' in line:
        idx = line.find("self.w['")
        if idx >= 0:
            i1 = idx + 8
            i2 = line.find("']", i1)
            if i2 >= 0:
                keys.add(line[i1:i2])
                continue
        idx = line.find('self.w["')
        if idx >= 0:
            i1 = idx + 8
            i2 = line.find('"]', i1)
            if i2 >= 0:
                keys.add(line[i1:i2])
                continue
for k in sorted(keys):
    print(k)
