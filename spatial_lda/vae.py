# source: https://github.com/wiseodd/generative-models/blob/master/VAE
# /vanilla_vae/vae_pytorch.py
import torch
import torch.nn.functional as nn
import torch.optim as optim
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from torch.autograd import Variable
import numpy as np
from dataset import *
import os
import gc
import pickle
from tqdm import tqdm

# Get file path
data_root = os.path.join(os.path.dirname(__file__), '../data')

# Hyperparameters and flags
NUM_KMEANS_CLUSTERS = 100
PICKLE_SAVE_RUN = False
IMAGE_MATRIX_PATH = os.path.join(data_root, "grayscale_img_matrix.pkl")

grayscaleDataset = ADE20K(root=getDataRoot(), transform=vae_transform,
                          useStringLabels=True, randomSeed=49)

# select most common label strings from tuples of (label, count)
mostCommonLabels = list(
    map(lambda x: x[0], grayscaleDataset.counter.most_common(5)))
grayscaleDataset.selectSubset(mostCommonLabels, normalizeWeights=True)

print("resized image size is: ", grayscaleDataset.__getitem__(0)[0].shape)
print(len(grayscaleDataset))

_, im_x, im_y = grayscaleDataset.__getitem__(0)[0].shape
grayscaleDataset.useOneHotLabels()

label_dim = grayscaleDataset.__getitem__(0)[1].shape
print(label_dim)

mb_size = 55
Z_dim = 250
X_dim = 224 * 224
y_dim = label_dim
# Change this to be a subset
h_dim = 128
c = 0
lr = 1e-3


def xavier_init(size):
    in_dim = size[0]
    xavier_stddev = 1. / np.sqrt(in_dim / 2.)
    return Variable(torch.randn(*size) * xavier_stddev, requires_grad=True)


# =============================== Q(z|X) ======================================

Wxh = xavier_init(size=[X_dim, h_dim])
bxh = Variable(torch.zeros(h_dim), requires_grad=True)

Whz_mu = xavier_init(size=[h_dim, Z_dim])
bhz_mu = Variable(torch.zeros(Z_dim), requires_grad=True)

Whz_var = xavier_init(size=[h_dim, Z_dim])
bhz_var = Variable(torch.zeros(Z_dim), requires_grad=True)


def Q(X):
    h = nn.relu(X @ Wxh + bxh.repeat(X.size(0), 1))
    z_mu = h @ Whz_mu + bhz_mu.repeat(h.size(0), 1)
    z_var = h @ Whz_var + bhz_var.repeat(h.size(0), 1)
    return z_mu, z_var


def sample_z(mu, log_var):
    eps = Variable(torch.randn(mb_size, Z_dim))
    return mu + torch.exp(log_var / 2) * eps


# =============================== P(X|z) ======================================

Wzh = xavier_init(size=[Z_dim, h_dim])
bzh = Variable(torch.zeros(h_dim), requires_grad=True)

Whx = xavier_init(size=[h_dim, X_dim])
bhx = Variable(torch.zeros(X_dim), requires_grad=True)


def P(z):
    h = nn.relu(z @ Wzh + bzh.repeat(z.size(0), 1))
    X = nn.sigmoid(h @ Whx + bhx.repeat(h.size(0), 1))
    return X


# =============================== TRAINING ====================================

params = [Wxh, bxh, Whz_mu, bhz_mu, Whz_var, bhz_var,
          Wzh, bzh, Whx, bhx]

solver = optim.Adam(params, lr=lr)

for epoch in range(500):
    loader = get_single_loader(dataset=grayscaleDataset, batch_size=mb_size,
                               shuffle_dataset=True, random_seed=epoch)
    bar = tqdm(total=len(grayscaleDataset), desc="epoch num: %d" % epoch)

    for batch_num, (X, Y) in enumerate(loader):

        X = Variable(torch.flatten(X, start_dim=1))

        # Forward
        z_mu, z_var = Q(X)
        z = sample_z(z_mu, z_var)
        X_sample = P(z)

        # Loss
        recon_loss = nn.binary_cross_entropy(X_sample, X,
                                             size_average=False) / mb_size
        kl_loss = torch.mean(
            0.5 * torch.sum(torch.exp(z_var) + z_mu ** 2 - 1. - z_var, 1))
        loss = recon_loss + kl_loss

        # Backward
        loss.backward()

        # Update
        solver.step()

        # Housekeeping
        for p in params:
            if p.grad is not None:
                data = p.grad.data
                p.grad = Variable(data.new().resize_as_(data).zero_())
        # Print and plot every now and then
        if batch_num % 20 == 0:
            print('Iter-{}; Loss: {:.4}'.format(batch_num, loss.item()))

            samples = P(z).data.numpy()[:16]

            fig = plt.figure(figsize=(4, 4))
            gs = gridspec.GridSpec(4, 4)
            gs.update(wspace=0.05, hspace=0.05)

            for i, sample in enumerate(samples):
                ax = plt.subplot(gs[i])
                plt.axis('off')
                ax.set_xticklabels([])
                ax.set_yticklabels([])
                ax.set_aspect('equal')
                plt.imshow(sample.reshape(224, 224), cmap='Greys_r')

            if not os.path.exists('out/'):
                os.makedirs('out/')

            plt.savefig('out/{}.png'.format(str(c).zfill(3)),
                        bbox_inches='tight')
            c += 1
            plt.close(fig)

        bar.update(mb_size)
    gc.collect()
    bar.close()
    pickle.dump(params, open("out/vaeparams.pkl", "wb"))
