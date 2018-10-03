'''Noise-resistant heart rate analysis module for Python

#Reference:
van Gent, P., Farah, H., van Nes, N., & van Arem, B. (2018). Heart Rate Analysis for Human Factors: Development and Validation of an Open Source Toolkit for Noisy Naturalistic Heart Rate Data. In Proceedings of the 6th HUMANIST Conference (pp. 173–178)

See also:
http://www.paulvangent.com/2016/03/15/analyzing-a-discrete-heart-rate-signal-using-python-part-1/
http://www.paulvangent.com/2016/03/21/analyzing-a-discrete-heart-rate-signal-using-python-part-2/
http://www.paulvangent.com/2016/03/30/analyzing-a-discrete-heart-rate-signal-using-python-part-3/
<part 4 to follow after publication>
'''

from datetime import datetime
import time

import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.signal import butter, filtfilt, welch, periodogram

__author__ = "Paul van Gent"
__version__ = "Version 0.8.2"
__license__ = "GNU General Public License V3.0"

measures = {}
working_data = {}

#Data handling
def get_data(filename, delim=',', column_name='None', encoding=None):
    '''Loads data from a .CSV or .MAT file into numpy array.

    Keyword Arguments:
    filename -- absolute or relative path to the file object to read
    delim -- the delimiter used if CSV file passed, (default ',')
    column_name -- for CSV files with header: specify column that contains the data
                   for matlab files it specifies the table name that contains the data
                   (default 'None')
    '''
    file_ext = filename.split('.')[-1]
    if file_ext == 'csv' or file_ext == 'txt':
        if column_name != 'None':
            hrdata = np.genfromtxt(filename, delimiter=delim, names=True, dtype=None, encoding=None)
            try:
                hrdata = hrdata[column_name]
            except Exception as error:
                print('\nError loading column "%s" from file "%s". \
                Is column name specified correctly?\n' %(column_name, filename))
                print('------\nError message: ' + str(error) + '\n------')
        elif column_name == 'None':
            hrdata = np.genfromtxt(filename, delimiter=delim, dtype=np.float64)
        else:
            print('\nError: column name "%s" not found in header of "%s".\n'
                  %(column_name, filename))
    elif file_ext == 'mat':
        print('getting matlab file')
        import scipy.io
        data = scipy.io.loadmat(filename)
        if column_name != "None":
            hrdata = np.array(data[column_name][:, 0], dtype=np.float64)
        else:
            print("\nError: column name required for Matlab .mat files\n\n")
    else:
        print('unknown file format')
        return None
    return hrdata

#Preprocessing
def scale_data(data):
    '''Scales data between 0 and 1024 for analysis
    
    Keyword arguments:
    data -- numpy array or list to be scaled
    '''
    range = np.max(data) - np.min(data)
    minimum = np.min(data)
    data = 1024 * ((data - minimum) / range)
    return data

def enhance_peaks(hrdata, iterations=2):
    '''Attempts to enhance the signal-noise ratio by accentuating the highest peaks
    note: denoise first
    
    Keyword arguments:
    hrdata -- numpy array or list containing heart rate data
    iterations -- the number of scaling steps to perform (default=3)
    '''
    scale_data(hrdata)
    for i in range(iterations):
        hrdata = np.power(hrdata, 2)
        hrdata = scale_data(hrdata)
    return hrdata    

def mark_clipping(hrdata, threshold):
    '''function that marks start and end of clipping part
    it detects the start and end of clipping segments and returns them
    
    keyword arguments:
    - data: 1d list or numpy array containing heart rate data
    - threshold: the threshold for clipping, recommended to
                 be a few data points below ADC or sensor max value, 
                 to compensate for signal noise (default 1020)
    
    '''
    clip_binary = np.where(hrdata > threshold)
    clipping_edges = np.where(np.diff(clip_binary) > 1)[1]

    clipping_segments = []

    for i in range(0, len(clipping_edges)):
        if i == 0: #if first clipping segment
            clipping_segments.append((clip_binary[0][0], 
                                      clip_binary[0][clipping_edges[0]]))
        elif i == len(clipping_edges):
            #append last entry
            clipping_segments.append((clip_binary[0][clipping_edges[i]+1],
                                      clip_binary[0][-1]))    
        else:
            clipping_segments.append((clip_binary[0][clipping_edges[i-1] + 1],
                                      clip_binary[0][clipping_edges[i]]))

    return clipping_segments

def interpolate_peaks(hrdata, sample_rate, threshold=1020):
    '''function that interpolates peaks between
    the clipping segments using cubic spline interpolation.
    
    It takes the clipping start +/- 100ms to calculate the spline.
    
    Returns full data array with interpolated segments patched in
    
    keyword arguments:
    data - 1d list or numpy array containing heart rate data
    clipping_segments - list containing tuples of start- and 
                        end-points of clipping segments.
    '''
    clipping_segments = mark_clipping(hrdata, threshold)
    num_datapoints = int(0.1 * sample_rate)
    newx = []
    newy = []
    
    for segment in clipping_segments:
        if segment[0] < num_datapoints: 
            #if clipping is present at start of signal, skip.
            #We cannot interpolate accurately when there is insufficient data prior to clipping segment.
            pass
        else: 
            antecedent = hrdata[segment[0] - num_datapoints : segment[0]]
            consequent = hrdata[segment[1] : segment[1] + num_datapoints]
            segment_data = np.concatenate((antecedent, consequent))
        
            interpdata_x = np.concatenate(([x for x in range(segment[0] - num_datapoints, segment[0])],
                                            [x for x in range(segment[1], segment[1] + num_datapoints)]))
            x_new = np.linspace(segment[0] - num_datapoints,
                                segment[1] + num_datapoints,
                                ((segment[1] - segment[0]) + (2 * num_datapoints)))
        
            interp_func = UnivariateSpline(interpdata_x, segment_data, k=3)
            interp_data = interp_func(x_new)
        
            hrdata[segment[0] - num_datapoints :
                    segment[1] + num_datapoints] = interp_data
       
    return hrdata

def raw_to_ecg(hrdata, enhancepeaks=False):
    '''Flips raw signal with negative mV peaks to normal ECG

    Keyword arguments:
    hrdata -- numpy array or list containing raw heart rate data
    enhancepeaks -- boolean, whether to apply peak accentuation (default False)
    '''
    hrmean = np.mean(hrdata)
    hrdata = (hrmean - hrdata) + hrmean
    if enhancepeaks:
        hrdata = enhance_peaks(hrdata)
    return hrdata

def get_samplerate_mstimer(timerdata):
    '''Determines sample rate of data from ms-based timer.

    Keyword arguments:
    timerdata -- array containing values of a timer, in ms
    '''
    sample_rate = ((len(timerdata) / (timerdata[-1]-timerdata[0]))*1000)
    working_data['sample_rate'] = sample_rate
    return sample_rate

def get_samplerate_datetime(datetimedata, timeformat='%H:%M:%S.%f'):
    '''Determines sample rate of data from datetime-based timer.

    Keyword arguments:
    timerdata -- array containing values of a timer, datetime strings
    timeformat -- the format of the datetime-strings in datetimedata
    default('%H:%M:%S.f', 24-hour based time including ms: 21:43:12.569)
    '''
    datetimedata = np.asarray(datetimedata, dtype='str') #cast as str in case of np.bytes type
    elapsed = ((datetime.strptime(datetimedata[-1], timeformat) -
                datetime.strptime(datetimedata[0], timeformat)).total_seconds())
    sample_rate = (len(datetimedata) / elapsed)
    working_data['sample_rate'] = sample_rate
    return sample_rate

def rollwindow(data, windowsize):
    '''Returns rolling window of size 'window' over dataset 'data'.

    Keyword arguments:
    data -- 1-dimensional numpy array
    window -- window size
    '''
    shape = data.shape[:-1] + (data.shape[-1] - windowsize + 1, windowsize)
    strides = data.strides + (data.strides[-1],)
    return np.lib.stride_tricks.as_strided(data, shape=shape, strides=strides)

def rolmean(data, windowsize, sample_rate):
    '''Calculates the rolling mean over passed data.

    Keyword arguments:
    data -- 1-dimensional numpy array or list
    windowsize -- the window size to use, in seconds (calculated as windowsize * sample_rate)
    sample_rate -- the sample rate of the data set
    '''
    avg_hr = (np.mean(data))
    data_arr = np.array(data)
    rol_mean = np.mean(rollwindow(data_arr, int(windowsize*sample_rate)), axis=1)
    missing_vals = np.array([avg_hr for i in range(0, int(abs(len(data_arr) - len(rol_mean))/2))])
    rol_mean = np.insert(rol_mean, 0, missing_vals)
    rol_mean = np.append(rol_mean, missing_vals)

    if len(rol_mean) != len(data):
        lendiff = len(rol_mean) - len(data)
        if lendiff < 0:
            rol_mean = np.append(rol_mean, 0)
        else:
            rol_mean = rol_mean[:-1]            
    return rol_mean

def butter_lowpass(cutoff, sample_rate, order=2):
    '''Defines standard Butterworth lowpass filter.

    use 'butter_lowpass_filter' to call the filter.
    '''
    nyq = 0.5 * sample_rate
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

def butter_lowpass_filter(data, cutoff, sample_rate, order):
    '''Applies the Butterworth lowpass filter

    Keyword arguments:
    data -- 1-dimensional numpy array or list containing the to be filtered data
    cutoff -- the cutoff frequency of the filter
    sample_rate -- the sample rate of the data set
    order -- the filter order (default 2)
    '''
    b, a = butter_lowpass(cutoff, sample_rate, order=order)
    filtered_data = filtfilt(b, a, data)
    return filtered_data

def filtersignal(data, cutoff, sample_rate, order):
    '''Filters the given signal using a Butterworth lowpass filter.

    Keyword arguments:
    data -- 1-dimensional numpy array or list containing the to be filtered data
    cutoff -- the cutoff frequency of the filter
    sample_rate -- the sample rate of the data set
    order -- the filter order (default 2)
    '''
    data = np.power(np.array(data), 3)
    filtered_data = butter_lowpass_filter(data, cutoff, sample_rate, order)
    return filtered_data

def MAD(data):
    '''function to compute median absolute deviation of data slice
       https://en.wikipedia.org/wiki/Median_absolute_deviation
    
    keyword arguments:
    - data: 1-dimensional numpy array containing data
    '''
    med = np.median(data)
    return np.median(np.abs(data - med))

def hampelfilt(data, filtsize=6):
    '''function to detect outliers based on hampel filter
       filter takes datapoint and six surrounding samples.
       Detect outliers based on being more than 3std from window mean
    
    keyword arguments:
    - data: 1-dimensional numpy array containing data
    - filtsize: the filter size expressed the number of datapoints
                taken surrounding the analysed datapoint. a filtsize
                of 6 means three datapoints on each side are taken.
                total filtersize is thus filtsize + 1 (datapoint evaluated)
    '''
    output = [x for x in data] #generate second list to prevent overwriting first
    onesided_filt = filtsize // 2
    #madarray = [0 for x in range(0, onesided_filt)]
    for i in range(onesided_filt, len(data) - onesided_filt - 1):
        dataslice = output[i - onesided_filt : i + onesided_filt]
        mad = MAD(dataslice)
        median = np.median(dataslice)
        if output[i] > median + (3 * mad):
            output[i] = median
    return output

def hampel_correcter(data, sample_rate, filtsize=6):
    '''Returns difference between data and large windowed hampel median filter.
       Results in strong noise suppression, but relatively expensive to compute.
    '''
    return data - hampelfilt(data, filtsize=int(sample_rate))

#Peak detection
def detect_peaks(hrdata, rol_mean, ma_perc, sample_rate, update_dict=True):
    '''Detects heartrate peaks in the given dataset.

    Keyword arguments:
    hr data -- 1-dimensional numpy array or list containing the heart rate data
    rol_mean -- 1-dimensional numpy array containing the rolling mean of the heart rate signal
    ma_perc -- the percentage with which to raise the rolling mean,
    used for fitting detection solutions to data
    sample_rate -- the sample rate of the data set
    update_dict -- whether to update the peak information in the module's data structure
                   Setting this to False (default True) allows peak function to be re-used for
                   example by the breath analysis module.
    '''
    rmean = np.array(rol_mean)
    rol_mean = rmean + ((rmean / 100) * ma_perc)
    peaksx = np.where((hrdata > rol_mean))[0]
    peaksy = hrdata[np.where((hrdata > rol_mean))[0]]
    peakedges = np.concatenate((np.array([0]),
                                (np.where(np.diff(peaksx) > 1)[0]),
                                np.array([len(peaksx)])))
    peaklist = []

    for i in range(0, len(peakedges)-1):
        try:
            y_values = peaksy[peakedges[i]:peakedges[i+1]].tolist()
            peaklist.append(peaksx[peakedges[i] + y_values.index(max(y_values))])
        except:
            pass

    if update_dict:
        working_data['peaklist'] = peaklist
        working_data['ybeat'] = [hrdata[x] for x in peaklist]
        working_data['rolmean'] = rol_mean
        calc_rr(sample_rate)
        if len(working_data['RR_list']):
            working_data['rrsd'] = np.std(working_data['RR_list'])
        else:
            working_data['rrsd'] = np.inf
    else:
        return peaklist

def fit_peaks(hrdata, rol_mean, sample_rate, bpmmin=40, bpmmax=180):
    '''Runs fitting with varying peak detection thresholds given a heart rate signal.
       Results in relatively noise-robust, temporally accuract peak detection, as no
       non-linear transformations are involved that might shift peak positions.

    Keyword arguments:
    hrdata - 1-dimensional numpy array or list containing the heart rate data
    rol_mean -- 1-dimensional numpy array containing the rolling mean of the heart rate signal
    sample_rate -- the sample rate of the data set
    bpmmin -- minimum value of bpm to see as likely (default 40)
    bpmmax -- maximum value of bpm to see as likely (default 180)
    '''
    ma_perc_list = [5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 150, 200, 300]
    rrsd = []
    valid_ma = []
    for ma_perc in ma_perc_list:
        detect_peaks(hrdata, rol_mean, ma_perc, sample_rate)
        bpm = ((len(working_data['peaklist'])/(len(hrdata)/sample_rate))*60)
        rrsd.append([working_data['rrsd'], bpm, ma_perc])

    for _rrsd, _bpm, _ma_perc in rrsd:
        if (_rrsd > 0.1) and ((bpmmin <= _bpm <= bpmmax)):
            valid_ma.append([_rrsd, _ma_perc])


    working_data['best'] = min(valid_ma, key=lambda t: t[0])[1]
    detect_peaks(hrdata, rol_mean, min(valid_ma, key=lambda t: t[0])[1], sample_rate)

def check_peaks(reject_segmentwise=False):
    '''Determines the best fit for peak detection variations run by fit_peaks().'''
    rr_arr = np.array(working_data['RR_list'])
    peaklist = np.array(working_data['peaklist'])
    ybeat = np.array(working_data['ybeat'])
    mean_rr = np.mean(rr_arr)
    upper_threshold = mean_rr + 300 if (0.3 * mean_rr) <= 300 else mean_rr + (0.3 * mean_rr)
    lower_threshold = mean_rr - 300 if (0.3 * mean_rr) <= 300 else mean_rr - (0.3 * mean_rr)

    peaklist_cor = peaklist[np.where((rr_arr > lower_threshold) &
                                     (rr_arr < upper_threshold))[0]+1]
    working_data['peaklist_cor'] = np.insert(peaklist_cor, 0, peaklist[0])
    working_data['removed_beats'] = peaklist[np.where((rr_arr <= lower_threshold) |
                                                      (rr_arr >= upper_threshold))[0]+1]
    working_data['removed_beats_y'] = ybeat[np.where((rr_arr <= lower_threshold) |
                                                     (rr_arr >= upper_threshold))[0]+1]
    working_data['binary_peaklist'] = [0 if x in working_data['removed_beats'] 
                                       else 1 for x in working_data['peaklist']]
    if(reject_segmentwise): 
        check_binary_quality(working_data['binary_peaklist'])
    update_rr()

def check_binary_quality(binary_peaklist, maxrejects=3):
    '''Checks signal in chunks of 10 beats. 
    Zeros out chunk if number of rejected peaks > maxrejects.
    Also marks rejected segment coordinates in tuples (x[0], x[1] in working_data['rejected_segments']
    
    Keyword arugments:
    binary_peaklist: list with 0 and 1 corresponding to r-peak accept/reject decisions
    maxrejects: int, maximum number of rejected peaks per 10-beat window (default 3)
    '''
    idx = 0
    peaklist = working_data['peaklist']
    working_data['rejected_segments'] = []
    for i in range(int(len(binary_peaklist) / 10)):
        if np.bincount(binary_peaklist[idx:idx + 10])[0] > maxrejects:
            binary_peaklist[idx:idx + 10] = [0 for i in range(len(binary_peaklist[idx:idx+10]))]
            if idx + 10 < len(peaklist): 
                working_data['rejected_segments'].append((peaklist[idx], peaklist[idx + 10]))
            else:
                working_data['rejected_segments'].append((peaklist[idx], peaklist[-1]))
        idx += 10

#Calculating all measures
def calc_rr(sample_rate):
    '''Calculates the R-R (peak-peak) data required for further analysis.

    Uses calculated measures stored in the working_data{} dict to calculate
    all required peak-peak datasets. Stores results in the working_data{} dict.

    Keyword arguments:
    sample_rate -- the sample rate of the data set
    '''
    peaklist = np.array(working_data['peaklist'])

    #delete first peak if within first 150ms (signal might start mid-beat after peak)
    if len(peaklist) > 0:
        if peaklist[0] <= ((sample_rate / 1000.0) * 150):
            peaklist = np.delete(peaklist, 0)
            working_data['peaklist'] = peaklist
            working_data['ybeat'] = np.delete(working_data['ybeat'], 0)

    rr_list = (np.diff(peaklist) / sample_rate) * 1000.0
    rr_diff = np.abs(np.diff(rr_list))
    rr_sqdiff = np.power(rr_diff, 2)
    working_data['RR_list'] = rr_list
    working_data['RR_diff'] = rr_diff
    working_data['RR_sqdiff'] = rr_sqdiff

def update_rr():
    '''Updates RR differences and RR squared differences based on corrected RR list

    Uses information about rejected peaks to update RR_list_cor, and RR_diff, RR_sqdiff
    in the working_data{} dict.
    '''
    rr_source = working_data['RR_list']
    b_peaks = working_data['binary_peaklist']
    rr_list = [rr_source[i] for i in range(len(rr_source)) if b_peaks[i] + b_peaks[i+1] == 2]
    rr_mask = [0 if (b_peaks[i] + b_peaks[i+1] == 2) else 1 for i in range(len(rr_source))]
    rr_masked = np.ma.array(rr_source, mask=rr_mask)
    rr_diff = np.abs(np.diff(rr_masked))
    rr_diff = rr_diff[~rr_diff.mask]
    rr_sqdiff = np.power(rr_diff, 2)
    
    working_data['RR_masklist'] = rr_mask
    working_data['RR_list_cor'] = rr_list
    working_data['RR_diff'] = rr_diff
    working_data['RR_sqdiff'] = rr_sqdiff

def calc_ts_measures():
    '''Calculates the time-series measurements.

    Uses calculated measures stored in the working_data{} dict to calculate
    the time-series measurements of the heart rate signal.
    Stores results in the measures{} dict object.
    '''
    rr_list = working_data['RR_list_cor']
    rr_diff = working_data['RR_diff']
    rr_sqdiff = working_data['RR_sqdiff']
    
    measures['bpm'] = 60000 / np.mean(rr_list)
    measures['ibi'] = np.mean(rr_list)
    measures['sdnn'] = np.std(rr_list)
    measures['sdsd'] = np.std(rr_diff)
    measures['rmssd'] = np.sqrt(np.mean(rr_sqdiff))
    nn20 = [x for x in rr_diff if x > 20]
    nn50 = [x for x in rr_diff if x > 50]
    measures['nn20'] = nn20
    measures['nn50'] = nn50
    measures['pnn20'] = float(len(nn20)) / float(len(rr_diff))
    measures['pnn50'] = float(len(nn50)) / float(len(rr_diff))
    measures['hr_mad'] = MAD(rr_list)

def calc_fd_measures(hrdata, sample_rate, method='welch'):
    '''Calculates the frequency-domain measurements.

    Uses calculated measures stored in the working_data{} dict to calculate
    the frequency-domain measurements of the heart rate signal.
    Stores results in the measures{} dict object.
    '''
    rr_list = working_data['RR_list_cor']
    rr_x = []
    pointer = 0
    for x in rr_list:
        pointer += x
        rr_x.append(pointer)
    rr_x_new = np.linspace(rr_x[0], rr_x[-1], rr_x[-1])
    interpolated_func = UnivariateSpline(rr_x, rr_list, k=3)
    
    if method=='fft':
        datalen = len(rr_x_new)
        frq = np.fft.fftfreq(datalen, d=((1/1000.0)))
        frq = frq[range(int(datalen/2))]
        Y = np.fft.fft(interpolated_func(rr_x_new))/datalen
        Y = Y[range(int(datalen/2))]
        psd = np.power(Y, 2)
    elif method=='periodogram':
        frq, psd = periodogram(interpolated_func(rr_x_new), fs=1000.0)
    elif method=='welch':
        frq, psd = welch(interpolated_func(rr_x_new), fs=1000.0, nperseg=100000)
    else:
        print("specified method incorrect, use 'fft', 'periodogram' or 'welch'")
        raise SystemExit(0)
    
    measures['lf'] = np.trapz(abs(psd[(frq >= 0.04) & (frq <= 0.15)]))
    measures['hf'] = np.trapz(abs(psd[(frq >= 0.16) & (frq <= 0.5)]))
    measures['lf/hf'] = measures['lf'] / measures['hf']
    measures['interp_rr_function'] = interpolated_func
    measures['interp_rr_linspace'] = (rr_x[0], rr_x[-1], rr_x[-1])

def calc_breathing(sample_rate):
    '''function to estimate breathing rate from heart rate signal.
    
    Upsamples the list of detected rr_intervals by interpolation
    then tries to extract breathing peaks in the signal.

    keyword arguments:
    sample_rate -- sample rate of the heart rate signal
    '''
    rrlist = working_data['RR_list_cor']
    x = np.linspace(0, len(rrlist), len(rrlist))
    x_new = np.linspace(0, len(rrlist), len(rrlist)*10)
    interp = UnivariateSpline(x, rrlist, k=3)
    breathing = interp(x_new)
    breathing_rolmean = rolmean(breathing, 0.75, 100.0)
    peaks = detect_peaks(breathing, breathing_rolmean, 1, sample_rate, update_dict=False)
    
    if len(peaks) > 1:
        signaltime = len(working_data['hr']) / sample_rate
        measures['breathingrate'] = len(peaks) / signaltime
    else:
        measures['breathingrate'] = np.nan

#Plotting it
def plotter(show=True, title='Heart Rate Signal Peak Detection', reject_segmentwise=False):
    '''Plots the analysis results.

    Uses calculated measures and data stored in the working_data{} and measures{}
    dict objects to visualise the fitted peak detection solution.

    Keyword arguments:
    show -- whether to display the plot (True) or return a plot object (False) (default True)
    title -- the title used in the plot
    '''
    import matplotlib.pyplot as plt
    peaklist = working_data['peaklist']
    ybeat = working_data['ybeat']
    rejectedpeaks = working_data['removed_beats']
    rejectedpeaks_y = working_data['removed_beats_y']
    plt.title(title)
    plt.plot(working_data['hr'], alpha=0.5, color='blue', label='heart rate signal')
    plt.scatter(peaklist, ybeat, color='green', label='BPM:%.2f' %(measures['bpm']))
    plt.scatter(rejectedpeaks, rejectedpeaks_y, color='red', label='rejected peaks')
    if(reject_segmentwise):
        for segment in working_data['rejected_segments']:
            plt.axvspan(segment[0], segment[1], facecolor='red', alpha=0.5)
    plt.legend(loc=4, framealpha=0.6)
    if show:
        plt.show()
    else:
        return plt

#Wrapper function
def process(hrdata, sample_rate, windowsize=0.75, report_time=False, 
            calc_freq=False, freq_method='welch', interp_clipping=True, clipping_scale=False,
            interp_threshold=1020, hampel_correct=False, bpmmin=40, bpmmax=180,
            reject_segmentwise=False):
    '''Processed the passed heart rate data. Returns measures{} dict containing results.

    Keyword arguments:
    hrdata -- 1-dimensional numpy array or list containing heart rate data
    sample_rate -- the sample rate of the heart rate data
    windowsize -- the window size to use, in seconds (calculated as windowsize * sample_rate)
    report_time -- whether to report total processing time of algorithm (default True)
    calc_freq -- whether to compute time-series measurements (default False)
    interp_clipping -- whether to detect and interpolate clipping segments of the signal 
                       (default True)
    intep_threshold -- threshold to use to detect clipping segments. Recommended to be a few
                       datapoints below the sensor or ADC's maximum value (to account for
                       slight data line noise). Default 1020, 4 below max of 1024 for 10-bit ADC
    hampel_correct -- whether to reduce noisy segments using large median filter. Disabled by
                      default due to computational complexity, and generally it is not necessary
    bpmmin -- minimum value to see as likely for BPM when fitting peaks
    bpmmax -- maximum value to see as likely for BPM when fitting peaks
    '''
    t1 = time.clock()

    if interp_clipping:
        if clipping_scale:
            hrdata = scale_data(hrdata)
        hrdata = interpolate_peaks(hrdata, sample_rate, threshold=interp_threshold)

    if hampel_correct:
        hrdata = enhance_peaks(hrdata)
        hrdata = hampel_correcter(hrdata, sample_rate, filtsize=sample_rate)

    working_data['hr'] = hrdata
    rol_mean = rolmean(hrdata, windowsize, sample_rate)
    fit_peaks(hrdata, rol_mean, sample_rate)
    calc_rr(sample_rate)
    check_peaks(reject_segmentwise)
    calc_ts_measures()
    calc_breathing(sample_rate)
    if calc_freq:
        calc_fd_measures(hrdata, sample_rate)
    if report_time:
        print('\nFinished in %.8s sec' %(time.clock()-t1))
    return measures

if __name__ == '__main__':
    hrdata = get_data('data.csv')
    fs = 100.0

    #hrdata = get_data('data2.csv', column_name = 'hr')
    #fs = get_samplerate_mstimer(get_data('data2.csv', column_name='timer'))

    measures = process(hrdata, fs, report_time=True, calc_freq =True, interp_clipping=True, hampel_correct=False)

    for m in measures.keys():
        print(m + ': ' + str(measures[m]))
    
    plotter()