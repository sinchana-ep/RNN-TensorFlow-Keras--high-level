import argparse
import pickle
import re
from collections import Counter

import tensorflow as tf
from matplotlib import pyplot as plt


def files_to_tfrecord_dynamic(*files, out_path, regex, maxlen=0, plot=False):
    """
    Process a number of text files into TFRecords data file.

    All files are conjoined into one big string. Then, this string is split
    according to the requested regular expression. Furthermore, a special
    "beginning-of-sequence" character is prepended to each sequence and an
    "end-of-sequence" character appended. The characters are mapped to integer
    indices representing one-hot vectors. We store the processed sequences into
    a TFrecords file; we also store the character-index mapping (vocabulary).

    Parameters:
        files: Paths to the text files to use for the corpus.
        out_path: Path to store the processed corpus, *without* file extension!
        regex: Should *not* be a compiled regular expression, just a
               corresponding string!
        maxlen: Int, all sequences longer than this will be removed from the
                dataset. The default (0) makes this inactive
        plot: Produce a histogram plot of sequence lengths at the end.
    """
    full_text = "\n".join(open(file).read() for file in files)
    # we create a mapping from characters to integers, including special characters
    chars = set(full_text)
    ch_to_ind = dict(zip(chars, range(3, len(chars)+3)))
    ch_to_ind["<PAD>"] = 0
    ch_to_ind["<S>"] = 1
    ch_to_ind["</S>"] = 2

    seqs = text_to_seqs(full_text, regex, ch_to_ind)
    print("Split input into {} sequences...".format(len(seqs)))
    print("Longest sequence is {} characters. If this seems unreasonable, "
          "consider using the maxlen"
          " argument!".format(max(len(seq) for seq in seqs)))
    if maxlen:
        print("Removing sequences longer than {} characters...".format(maxlen))
        seqs = [seq for seq in seqs if len(seq) < maxlen]
        print("{} sequences remaining.".format(len(seqs)))
        print("Longest remaining sequence has length {}.".format(
            max(len(seq) for seq in seqs)))
    print("Removing length-0 sequences...")
    seqs = [seq for seq in seqs if len(seq) > 0]
    print("{} sequences remaining.".format(len(seqs)))

    with tf.io.TFRecordWriter(out_path + ".tfrecords") as writer:
        for ind, seq in enumerate(seqs):
            tfex = tf.train.Example(features=tf.train.Features(feature={
                "seq": tf.train.Feature(int64_list=tf.train.Int64List(value=seq))
            }))
            writer.write(tfex.SerializeToString())
            if (ind + 1) % 100 == 0:
                print("Serialized {} sequences...".format(ind+1))
    pickle.dump(ch_to_ind, open(out_path + "_vocab", mode="wb"))

    # plots
    if plot:
        len_counter = Counter(len(seq) for seq in seqs)
        lens = range(max(len_counter.keys()) + 1)

        len_freqs = [0]*len(lens)
        for leng in len_counter:
            len_freqs[leng] = len_counter[leng]

        plt.plot(lens, len_freqs)
        plt.title("Frequencies of sequence lengths")
        plt.xlabel("Sequence length")
        plt.ylabel("Frequency")
        plt.show()


def text_to_seqs(text, regex, mapping):
    """Convert a string to a list of lists of variable length.

    Each character is mapped to its index as given by the mapping parameter.

    Parameters:
        text: String, the corpus.
        regex: String representing the regular expression used to split the
               text.
        mapping: Dict mapping characters to indices.

    Returns:
        List of split character-index sequences.
    """
    split = re.split(regex, text)
    return [[mapping["<S>"]] + chs_to_inds(seq, mapping) +
            [mapping["</S>"]] for seq in split]


def chs_to_inds(char_list, mapping):
    """Helper to convert a list of characters to a list of corresponding indices.

    Parameters:
        char_list: List of characters (or string).
        mapping: Dict mapping characters to indices.

    Returns:
        List of character indices.
    """
    return [mapping[ch] for ch in char_list]


def parse_seq(example_proto):
    """Needed to read the stored .tfrecords data -- import this in your
    training script.

    Parameters:
        example_proto: Protocol buffer of single example.

    Returns:
        Tensor containing the parsed sequence.
    """
    features = {"seq": tf.io.VarLenFeature(tf.int64)}
    parsed_features = tf.io.parse_single_example(example_proto, features)
    sparse_seq = parsed_features["seq"]
    return tf.cast(tf.sparse.to_dense(sparse_seq), tf.int32)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data_files",
                        help="File paths to use as input, separated by commas."
                             " E.g. 'file1.txt,file2.txt'.")
    parser.add_argument("out_path",
                        help="Path to store the data to. Do *not* specify the "
                             "file extension, as this script stores both a "
                             ".tfrecords file as well as a vocabulary file.")
    parser.add_argument("regex",
                        help="Regex to use for splitting files into sequences")
    parser.add_argument("-m", "--maxlen",
                        type=int,
                        default=0,
                        help="Maximum length of characters per sequence. "
                             "Sequences longer than this will be removed. "
                             "Default: 0, meaning that all sequences are "
                             "taken.")
    parser.add_argument("-p", "--plot",
                        action="store_true",
                        help="If set, produces a frequency plot of sequence "
                             "lengths for the chosen data. Not functional in "
                             "notebooks. :(")
    args = parser.parse_args()
    file_list = args.data_files.split(",")
    files_to_tfrecord_dynamic(*file_list, out_path=args.out_path,
                              regex=args.regex, maxlen=args.maxlen,
                              plot=args.plot)
