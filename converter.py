import numpy as np
import pandas as pd

# from	 	https://github.com/paulvangentcom/heartrate_analysis_python
# docs at 	https://python-heart-rate-analysis-toolkit.readthedocs.io/en/latest/
import heartbeat as hb 

import csv

def clamp(x, mn, mx):
	if (x > mx):
		return mx
	if (x < mn):
		return mn
	return x

# custom int converter decorator to deal with null values
# clamps as well
# returns int(x) if the input isn't the string "null"
def intr(x):
	ret = x
	if (x=='null'):
		return 0
	return clamp(int(x), 0, 1024)

# Processing needs to be done for our custom CSV header
with open('data/record_1537397981102_00047BB63.csv', newline='') as csvfile:
	reader = csv.reader(csvfile)
	rawdata = [x for x in reader]
	header_index = 7
	header = rawdata[header_index]
	
	k = 0
	for row in rawdata:
		if len(row) < 1:
			continue
		if row[-1] == "start experiment":
			break
		k=k+1

	print("The start of the experiment was at line %i." % (k))

	body = np.array(rawdata[k:])
	data = pd.DataFrame(body, columns=header)

fs = hb.get_samplerate_mstimer([int(x) for x in data['unix_timestamp'].tolist()])

# print(np.floor(1000 / np.mean(diffs)) / 4)

voltages = np.array([intr(x) for x in data['heart_rate_voltage'].tolist()])
filtered = hb.butter_lowpass_filter(voltages, cutoff=np.floor(fs / 4), sample_rate=fs, order=3)
enhanced = hb.enhance_peaks(filtered, iterations=2)

measures = hb.process(
	enhanced,				# array-like
	fs,						# frequency
	report_time=True,		# print the time for processing
	calc_freq=True,			# calcuate frequency domain
	interp_clipping=False,	# implied peak is interpolated
	interp_threshold=940	# amp beyond which will be checked for clipping
)

# Visualize peaks for inspection
hb.plotter()
