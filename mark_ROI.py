import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from PIL import Image

image_path = "/media/szelesteya/F824D4D024D492CC/EMBED-images/all-calc-with-roi"

image = Image.open(image_path + '-png/1.2.826.0.1.3680043.8.498.10327661849041216903391175175366180169_conv.png')

image_array = np.array(image)

plt.imshow(image_array, cmap='gray')

roi_coords = [ 1294, 477, 1564, 781 ]

rectangle = patches.Rectangle((roi_coords[1], roi_coords[0]), roi_coords[3]-roi_coords[1], roi_coords[2]-roi_coords[0], linewidth=1, edgecolor='r', facecolor='none')

plt.gca().add_patch(rectangle)

plt.show()