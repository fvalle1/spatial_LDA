import argparse
from feature_extraction import evaluate_kmeans, build_histogram, \
    n_keypoints, n_cnn_keypoints, n_clusters, \
    feature_model, cnn_num_layers_removed, num_most_common_labels_used

import pickle
import os
import numpy as np
import matplotlib.pyplot as plt
from dataset import *


def main_eval_cli():
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--num_clusters", \
                        help="Number of clusters", type=int)
    parser.add_argument("-k", "--num_keypoints", \
                        help="Number of keypoints", type=int)
    parsed_args = vars(parser.parse_args())

    # Get params
    num_clusters = parsed_args["num_clusters"]
    num_keypoints = parsed_args["num_keypoints"]

    # Get paths to filenames
    f_kmeans = "/home/yaatehr/programs/spatial_LDA/data/kmeans_%s_clusters_" \
               "%s_keypoints.pkl" % (num_clusters, num_keypoints)
    f_descriptor = "/home/yaatehr/programs/spatial_LDA/data" \
                   "/image_descriptors_dictionary_%s_keypoints.pkl" % \
                   num_keypoints

    # For each, go through all our metrics
    for metric in ["l2", "l1", "kl"]:
        print("Metric is: {}, keypoints: {}, clusters: {}".format(metric,
                                                                  num_keypoints,
                                                                  num_clusters))
        # Load pickled files
        with open(f_kmeans, "rb") as f:
            kmeans = pickle.load(f)
        f.close()
        with open(f_descriptor, "rb") as f:
            descriptor_list = pickle.load(f)
        f.close()

        # Evaluate model with different params/hyperparams
        histogram_distance_dict = evaluate_kmeans(descriptor_list, kmeans,
                                                  num_clusters, metric=metric)
        print("Evaluation finished")
        # Pickle distance dictionary
        f_out_pickle = "/home/yaatehr/programs/spatial_LDA/data/EVAL_kmeans_" \
                       "%s_clusters_%s_keypoints_%s_metric.pkl" % (num_clusters,
                                                                   num_keypoints,
                                                                   metric)
        with open(f_out_pickle, "wb") as f:
            pickle.dump(histogram_distance_dict, f)
            f.close()
        print("Pickle file dumped at: {}".format(f_out_pickle))


def plot_histograms_for_labels(n_keypoints, n_clusters):
    label_path = "/home/yaatehr/programs/datasets/seg_data/images/dataset1/"
    letters = os.listdir(label_path)
    f_kmeans = "/home/yaatehr/programs/spatial_LDA/data/top25_sift/kmeans_" \
               "%s_clusters_" \
               "%s_keypoints.pkl" % (n_clusters, n_keypoints)
    f_descriptor = "/home/yaatehr/programs/spatial_LDA/data/top25_sift" \
                   "/image_descriptors_dictionary_%s_keypoints.pkl" % \
                   n_keypoints
    with open(f_kmeans, 'rb') as f:
        kmeans = pickle.load(f)
    with open(f_descriptor, 'rb') as f:
        descriptor_list = pickle.load(f)
    for l in letters:
        labels_path = os.path.join(label_path, l)
        labels = os.listdir(labels_path)
        for label in labels:
            singular_label_path = os.path.join(labels_path, label)
            print(singular_label_path)
            plot_histograms_per_label(singular_label_path, n_keypoints, kmeans,
                                      descriptor_list, 0.1)


def plot_histograms_for_dataset(n_keypoints, n_clusters,
                                num_most_common_labels_used, model,
                                percentage_plotted=.01,
                                cnn_num_layers_removed=None):
    save_root = getDirPrefix(num_most_common_labels_used, model,
                             cnn_num_layers_removed=cnn_num_layers_removed)
    feature_path = os.path.join(save_root,
                                "feature_matrix_%s_keypoints_%s_clusters" % (
                                n_keypoints, n_clusters))
    print("eval for root: \n", save_root)
    if not os.path.exists(feature_path):
        raise Exception(
            "Must be an existing param tuple\n path non-existant: %s" %
            feature_path)

    with open(feature_path, "rb") as f:
        feature_tup = pickle.load(f)

    if model == "sift":
        hist_list, index_mask = feature_tup
    else:
        hist_list = feature_tup
        index_mask = None

    transform = get_model_transform(model)

    dataset = ADE20K(root=getDataRoot(), transform=transform,
                     useStringLabels=True, randomSeed=49)
    mostCommonLabels = list(map(lambda x: x[0], dataset.counter.most_common(
        num_most_common_labels_used)))
    dataset.selectSubset(mostCommonLabels, normalizeWeights=True)
    if index_mask is not None:
        dataset.applyMask(index_mask)
    kmeans_path = os.path.join(save_root,
                               "kmeans_%s_clusters_%s_keypoints.pkl" % (
                               n_clusters, n_keypoints))
    if not os.path.exists(kmeans_path):
        kmeans_path = os.path.join(save_root,
                                   "batch_kmeans_%s_clusters_%s_keypoints.pkl" % (
                                   n_clusters, n_keypoints))

    f_descriptor = os.path.join(save_root,
                                "image_descriptors_dictionary_%s_keypoints.pkl" % n_keypoints)

    with open(kmeans_path, 'rb') as f:
        kmeans = pickle.load(f)
    with open(f_descriptor, 'rb') as f:
        descriptor_list = pickle.load(f)
    plot_prefix = "plots_%s_keypoints_%s_clusters/" % (n_keypoints, n_clusters)
    for label in dataset.class_indices.keys():
        labelIndices = dataset.class_indices[label]
        for i in labelIndices:
            f = dataset.image_paths[i]
            if np.random.random() < percentage_plotted:
                # Plot image histogram
                des = descriptor_list[f]
                histogram = build_histogram(des, kmeans, n_clusters)
                plt.plot(histogram)
        plt.xlabel("features bag of words")
        plt.title("Histogram distribution for label %s" % label)

        plot_folder = os.path.join(save_root, plot_prefix)
        if not os.path.exists(plot_folder):
            os.makedirs(plot_folder)
        plt.savefig(os.path.join(plot_folder,
                                 "histogram_distribution_label_%s.png" % (
                                 label,)))
        plt.close()


def main_aggregate_pkl_files():
    # Get files and paths
    kmeans_eval_dir = "/home/yaatehr/programs/spatial_LDA/data/"
    files = os.listdir(kmeans_eval_dir)
    kmeans_eval_files = [file for file in files if file.startswith("EVAL")]
    kmeans_eval_aggregate_dict = {}

    # Iterate through kmeans files
    for kmeans_file in kmeans_eval_files:
        split_fname = kmeans_file.split("_")
        num_clusters = split_fname[2]
        num_keypoints = split_fname[4]
        metric = split_fname[6]
        with open(os.path.join(kmeans_eval_dir, kmeans_file), "rb") as f:
            kmeans_eval_aggregate_dict[(num_clusters, num_keypoints, metric)] \
                = \
                pickle.load(f)
            f.close()

    # Dump pickle file information
    kmeans_aggregate_dict_file = \
        "/home/yaatehr/programs/spatial_LDA/data/kmeans_aggregate_eval_dict.pkl"
    with open(kmeans_aggregate_dict_file, "wb") as f:
        pickle.dump(kmeans_eval_aggregate_dict, f)
        f.close()


def plot_histograms_per_label(label_path, n_keypoints, kmeans, descriptor_list,
                              percentage_plotted=0.05):
    img_files = os.listdir(label_path)
    fig, ax = plt.subplots(1, 1)
    label = label_path.split("/")[-1]
    n_clusters = kmeans.cluster_centers_.shape[0]
    for f in img_files:
        if f[-3:] != 'jpg':
            continue
        if np.random.random() < percentage_plotted:
            # Plot image histogram
            des = descriptor_list[f]

            histogram = build_histogram(des, kmeans,
                                        kmeans.cluster_centers_.shape[0])
            plt.plot(histogram)
    plt.xlabel("features bag of words")
    plt.title(
        "Histogram distribution for label %s for %s keypoints and %s "
        "clusters" % (
        label, n_keypoints, n_clusters))
    plt.savefig(
        "plots/histogram_distribution_label_%s_%s_keypoints_%s_clusters.png" % (
        label, n_keypoints, n_clusters))
    plt.close()


def plot_all():
    # Helper function
    def compute_weighted_average():
        seg_data_path = "/home/yaatehr/programs/datasets/seg_data/images" \
                        "/training/"
        weight_dict = {}
        subfolders = os.listdir(seg_data_path)
        for subfolder in subfolders:
            label_classes = os.listdir(os.path.join(seg_data_path, subfolder))
            for label in label_classes:
                files = os.listdir(
                    os.path.join(seg_data_path, subfolder, label))
                weight_dict[label] = len([file for file in files if
                                          file.endswith(".jpg")])
        return weight_dict

    def compute_average_dist(kmeans_eval):
        weight_dict = compute_weighted_average()
        N = np.sum(list(weight_dict.values()))

    kmeans_eval_file = "/home/yaatehr/programs/spatial_LDA/data/top25_sift" \
                       "/kmeans_aggregate_eval_dict.pkl"
    with open(kmeans_eval_file, "rb") as f:
        kmeans_eval_dict = pickle.load(f)
        f.close()
    keys = list(kmeans_eval_dict.keys())
    for key in keys:
        metric = key[2]
        print(metric)
        if metric == "l2":
            pass
        if metric == "l1":
            print(kmeans_eval_dict[key])
        if metric == "kl":
            print(kmeans_eval_dict[key])


def eval_dataset():
    # Make dataset object
    dataset = ADE20K(root=getDataRoot(), useStringLabels=True, randomSeed=49)
    histogram = np.zeros(len(dataset.class_indices.keys()))

    # Iterate through labels
    for i, label in enumerate(dataset.class_indices.keys()):
        indices = dataset.class_indices[label]
        histogram[i] = len(indices)

    # Save fpath
    save_root = os.path.dirname(__file__)

    # Plotting
    plt.plot(histogram)
    plt.xlabel("Label No.")
    plt.ylabel("Num Samples")
    plt.title("Dataset Distribution")
    plt.savefig(os.path.join(save_root, "dataset_distribution.png"))


if __name__ == "__main__":
    plot_histograms_for_labels(300, 300)
