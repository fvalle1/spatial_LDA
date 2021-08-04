import numpy as np
import matplotlib as plt
from sklearn.cluster import KMeans, MiniBatchKMeans
from skimage.transform import rescale, resize
from dataset import ADE20K, get_single_loader, getDataRoot
import os
import pickle
from collections import Counter
from tqdm import tqdm
from sklearn.decomposition import IncrementalPCA
import matplotlib.pyplot as plt

# Hyperparameters
NUM_KMEANS_CLUSTERS = 100
data_root = os.path.join(os.path.dirname(__file__), '../data')

# File paths and data roots
YAATEH_DATA_ROOT = "/Users/yaatehr/Programs/spatial_LDA/data/seg_data/images" \
                   "/training"
BOX_DATA_ROOT = "/home/yaatehr/programs/datasets/seg_data/images/training"
PICKLE_SAVE_RUN = True


def get_matrix_path(edge_len, nlabels):
    return os.path.join(data_root,
                        "grayscale_img_matrix_%d_%d.pkl" % (edge_len, nlabels))


def stack_images_rows_with_pad(dataset, edge_len, nlabels):
    """
    If/when we use a transform this won't be necessary
    """
    path = get_matrix_path(edge_len, nlabels)

    print("checking baseline path: \n", path)
    if not os.path.exists(path):
        list_of_images = []
        label_list = []

        dataset = get_single_loader(dataset, batch_size=1, shuffle_dataset=True)
        bar = tqdm(total=len(dataset))

        for step, (img, label) in enumerate(dataset):
            list_of_images.append(img.flatten())
            label_list.append(label)
            if step % 50 == 0:
                bar.update(50)
        maxlen = max([len(x) for x in list_of_images])
        out = np.vstack([np.concatenate([b, np.zeros(maxlen - len(b))]) for b in
                         list_of_images])
        print(out.shape)
        out = (out, label_list)
        with open(path, 'wb') as f:
            pickle.dump(out, f)
        return out
    else:
        with open(path, 'rb') as f:
            return pickle.load(f)


def resize_im_shape(img_shape, maxEdgeLen=50):
    x, y = img_shape
    if x > y:
        maxEdge = x
    else:
        maxEdge = y

    scalefactor = maxEdgeLen / maxEdge
    remainderEdge = int(min(x, y) * scalefactor)
    if x > y:
        return maxEdgeLen, remainderEdge
    return remainderEdge, maxEdgeLen


def resize_im(im, edge_len):
    return resize(im, resize_im_shape(im.shape, maxEdgeLen=edge_len),
                  anti_aliasing=False)


def createFeatureVectors(max_edge_len, n_keypoints):
    grayscaleDataset = ADE20K(grayscale=True, root=getDataRoot(),
                              transform=lambda x: resize_im(x, max_edge_len),
                              useStringLabels=True, randomSeed=49)

    # Select most common label strings from tuples of (label, count)
    n_labels = 5
    mostCommonLabels = list(
        map(lambda x: x[0], grayscaleDataset.counter.most_common(n_labels)))
    grayscaleDataset.selectSubset(mostCommonLabels, normalizeWeights=True)
    print(len(grayscaleDataset.counter))
    print("resized image size is: ", grayscaleDataset.__getitem__(0)[0].shape)
    print("stacking and flattening images")

    stacked_images, label_list = stack_images_rows_with_pad(grayscaleDataset,
                                                            max_edge_len,
                                                            n_labels)
    print("stacked im shape: ", stacked_images.shape)
    n_clust = len(grayscaleDataset.class_indices.keys())

    pca_path = os.path.join(data_root,
                            "pca_%d_clust_%d_edgelen_%d_keypoints.pkl" % (
                            n_clust, max_edge_len, n_keypoints))
    print("for path:\n", pca_path)

    if os.path.exists(pca_path):
        U = pickle.load(open(pca_path, "rb"))
        print("Successfully loaded pca features")
    else:
        pca = IncrementalPCA(batch_size=79, n_components=n_keypoints)
        U = pca.fit_transform(stacked_images)
        pickle.dump(U, open(pca_path, "wb"))
        print("DUMPED PCA features")


    print('fitting KMEANS')
    print("U shape: ", U.shape)

    kmeans_path = os.path.join(data_root,
                               "kmeans_%d_clust_%d_edgelen_%d_keypoints.pkl" % (
                               n_clust, max_edge_len, n_keypoints))
    print("for path:\n", kmeans_path)
    if os.path.exists(kmeans_path):
        kmeans = pickle.load(open(kmeans_path, "rb"))
        print("Successfully loaded kmeans")
    else:
        kmeans = MiniBatchKMeans(n_clusters=n_clust).fit(U)
        pickle.dump(kmeans, open(kmeans_path, "wb"))
        print("DUMPED Kmeans Model with")

    prediction = kmeans.predict(U)
    path = os.path.join(data_root, "baseline_run_incremental_%d_%d.pkl" % (
    max_edge_len, n_keypoints))

    with open(path, "wb") as f:
        eval_tup = (prediction, label_list, kmeans, stacked_images.shape)
        pickle.dump(eval_tup, f)

    plot_prefix = "baseline_%d_clust_%d_edgelen_%d_kp" % (
    n_clust, max_edge_len, n_keypoints)
    label_subset = grayscaleDataset.class_indices.keys()
    label_to_predictions = {}
    for label in label_subset:
        labelIndices = grayscaleDataset.class_indices[label]
        histogram = np.zeros(n_clust)
        for i in labelIndices:
            f = grayscaleDataset.image_paths[i]
            # Plot image histogram
            desc = U[i, :].reshape(1, -1)
            prediction = kmeans.predict(desc).item()
            histogram[prediction] += 1.0
        histogram /= len(labelIndices)

        label_to_predictions[label] = histogram

        plt.plot(histogram)
        plt.xlabel("unlabeled classes")
        plt.ylabel("predictions %")
        plt.title("PCA Kmeans prediction distribution for label %s" % label)
        axes = plt.gca()
        axes.set_xlim([0, n_clust - 1])
        axes.set_ylim([0, 1.0])

        plot_folder = os.path.join(data_root, plot_prefix)
        if not os.path.exists(plot_folder):
            os.makedirs(plot_folder)
        plt.savefig(
            os.path.join(plot_folder, "pca_kmeans_label%s.png" % (label,)))
        plt.close()
    pickle.dump(label_to_predictions,
                open(os.path.join(plot_folder, "label_to_pred.pkl"), "wb"))


def create_latex_table(n_labels, max_edge_len, n_keypoints):
    plot_prefix = "baseline_%d_clust_%d_edgelen_%d_kp" % (
    n_labels, max_edge_len, n_keypoints)
    plot_folder = os.path.join(data_root + "/baselines_5", plot_prefix)
    print(plot_folder)
    label_to_predictions = pickle.load(
        open(os.path.join(plot_folder, "label_to_pred.pkl"), "rb"))

    latex_template = """
    \\begin{table}[H]
    \\begin{tabular}{%s}
    %s \\\\
    %s \\\\
    %s \\\\
    %s \\\\
    %s \\\\
    %s
    \\end{tabular}
    \\caption{Distribution over label predictions for PCA Kmeans clustering 
    with %d clusters resized to a mix dimension of (%d,%d)}
    \\label{Tab:baseline%dclust%dlen}
    \\end{table}
    """ % (
        "l" * (n_labels + 1),
        " & Clust. ".join(["Label"] + [str(i) for i in range(n_labels)]),
        *[" & ".join(
            [label] + np.around(label_to_predictions[label], decimals=3).astype(
                str).tolist()) for label in label_to_predictions],
        n_labels,
        max_edge_len,
        max_edge_len,
        n_labels,
        max_edge_len,
    )
    print(latex_template)


def createplot():
    plot_prefix1 = "baseline_%d_clust_%d_edgelen_%d_kp" % (5, 380, 5)
    plot_prefix2 = "baseline_%d_clust_%d_edgelen_%d_kp" % (5, 380, 75)

    plot_p1 = os.path.join(data_root + "/baselines_5", plot_prefix1)
    plot_p2 = os.path.join(data_root + "/baselines_5", plot_prefix2)
    # print(plot_folder)
    label_to_predictions1 = pickle.load(
        open(os.path.join(plot_p1, "label_to_pred.pkl"), "rb"))
    label_to_predictions2 = pickle.load(
        open(os.path.join(plot_p2, "label_to_pred.pkl"), "rb"))

    x = np.arange(5)  # the label locations
    width = 0.35  # the width of the bars

    for label in label_to_predictions1:

        fig, ax = plt.subplots()
        rects1 = ax.bar(x - width / 2,
                        np.around(label_to_predictions1[label], decimals=3),
                        width, label="5 PCA components")
        rects2 = ax.bar(x + width / 2,
                        np.around(label_to_predictions2[label], decimals=3),
                        width, label='75 PCA components')

        # Add some text for labels, title and custom x-axis tick labels, etc.
        ax.set_ylabel('Percent classified in cluster')
        ax.set_title('PCA Kmeans Classification Comparison for %s' % label)
        ax.set_xticks(x)
        ax.set_xticklabels(
            ["Clust 0", "Clust 1", "Clust 2", "Clust 3", "Clust 4"])
        ax.legend()

        def autolabel(rects):
            """Attach a text label above each bar in *rects*, displaying its
            height."""
            for rect in rects:
                height = rect.get_height()
                ax.annotate('{}'.format(height),
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points",
                            ha='center', va='bottom')

        autolabel(rects1)
        autolabel(rects2)

        fig.tight_layout()

        plt.savefig(os.path.join(data_root,
                                 "../pca_kmeans_comparison_%s.png" % (label)))


def main():
    # for i in range(300, 500, 20):
    # for j in range(5, 79, 10):
    # createFeatureVectors(i, j)
    # create_latex_table(5, i, j)
    createplot()

if __name__ == "__main__":
    main()
