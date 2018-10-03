import numpy as np
import pandas as pd
import heartbeat as hb
import csv
from collections import OrderedDict


# class myDict:
# 	def __init__(self, reader, header_index):
# 		# reader is a csv reader object
# 		rawdata = [x for x in reader]
# 		body = np.array(rawdata[header_index + 1:])
		
# 		self.header = rawdata[header_index]
# 		self.data = pd.DataFrame(body, columns=self.header)

# 	# # helper for print function, add whitespace to lines for a fixed width
# 	# def fixwidth(self, s, w):
# 	# 	return s + " " * (w - len(s))

# 	# # override print to show first three lines of the data
# 	# def __str__(self):
# 		return str(self.data)


with open('data/record_1537380012888_00047A8B3.csv', newline='') as csvfile:
	reader = csv.reader(csvfile)
	rawdata = [x for x in reader]
	header_index = 7
	header = rawdata[header_index]
	body = np.array(rawdata[header_index + 1:])
	data = pd.DataFrame(body, columns=header)

unix_timestamps = data['unix_timestamp'].tolist()
diffs = []
for i in range(1, len(unix_timestamps) - 1):
	m = int(unix_timestamps[i])
	n = int(unix_timestamps[i+1])
	diffs.append(n - m)

avg_hz = np.floor(1000 / np.mean(diffs))
std_hz = np.std(diffs)

def intr(x):
	ret = x
	if (x=='null'):
		return 0
	return int(x)

voltages = np.array([intr(x) for x in data['heart_rate_voltage'].tolist()])
# measures = hb.process(voltages, avg_hz)
measures = hb.process(
	voltages,				# array-like
	avg_hz,					# frequency
	report_time=True,		# print the time for processing
	calc_freq=True,			# calcuate frequency domain
	interp_clipping=False,	# implied peak is interpolated
	interp_threshold=1024	# amp beyond which will be checked for clipping
)

print(measures['bpm']) #returns BPM value
print(measures['rmssd']) # returns RMSSD HRV measure

hb.plotter()
