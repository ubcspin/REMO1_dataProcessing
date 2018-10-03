import numpy as np
import pandas as pd

# from	 	https://github.com/paulvangentcom/heartrate_analysis_python
# docs at 	https://python-heart-rate-analysis-toolkit.readthedocs.io/en/latest/
import heartbeat as hb 

import csv

# custom int converter decorator to deal with null values
# returns int(x) if the input isn't the string "null"
def intr(x):
	ret = x
	if (x=='null'):
		return 0
	return int(x)

# Processing needs to be done for our custom CSV header
with open('data/test.csv', newline='') as csvfile:
	reader = csv.reader(csvfile)
	rawdata = [x for x in reader]
	header_index = 7
	header = rawdata[header_index]
	body = np.array(rawdata[header_index + 1:])
	data = pd.DataFrame(body, columns=header)

# Calculate the frequency programmatically
unix_timestamps = data['unix_timestamp'].tolist()
diffs = []
for i in range(1, len(unix_timestamps) - 1):
	m = int(unix_timestamps[i])
	n = int(unix_timestamps[i+1])
	diffs.append(n - m)

# Note: timestamps are in milliseconds, so hz = 1000 / avg
avg_hz = np.floor(1000 / np.mean(diffs))

voltages = np.array([intr(x) for x in data['heart_rate_voltage'].tolist()])
enhanced = hb.enhance_peaks(voltages, iterations=2)

# measures = hb.process(voltages, avg_hz)
measures = hb.process(
	enhanced,				# array-like
	avg_hz,					# frequency
	report_time=True,		# print the time for processing
	calc_freq=True,			# calcuate frequency domain
	interp_clipping=False,	# implied peak is interpolated
	interp_threshold=1024	# amp beyond which will be checked for clipping
)

# Visualize peaks for inspection
hb.plotter()
