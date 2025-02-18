import argparse
import cv2
import numpy as np
import torch
import os
import time

from vedacore.image import imread, imwrite
from vedacore.misc import Config, color_val, load_weights
from vedacore.parallel import collate, scatter
from vedadet.datasets.pipelines import Compose
from vedadet.engines import build_engine


def parse_args():
    parser = argparse.ArgumentParser(description='Train a detector')
    parser.add_argument('config', help='config file path')
    parser.add_argument('imgname', help='image file name')

    args = parser.parse_args()
    return args


def prepare(cfg):
    if torch.cuda.is_available():
        device = torch.cuda.current_device()
    else:
        device = 'cpu'
    # device = 'cpu'
    engine = build_engine(cfg.infer_engine)

    engine.model.to(device)
    load_weights(engine.model, cfg.weights.filepath)

    data_pipeline = Compose(cfg.data_pipeline)
    return engine, data_pipeline, device


def plot_result(result, imgfp, class_names, outfp='out.jpg'):
    font_scale = 0.5
    bbox_color = 'green'
    text_color = 'green'
    thickness = 1

    bbox_color = color_val(bbox_color)
    text_color = color_val(text_color)
    img = imread(imgfp)

    bboxes = np.vstack(result)
    labels = [
        np.full(bbox.shape[0], idx, dtype=np.int32)
        for idx, bbox in enumerate(result)
    ]
    labels = np.concatenate(labels)

    for bbox, label in zip(bboxes, labels):
        bbox_int = bbox[:4].astype(np.int32)
        left_top = (bbox_int[0], bbox_int[1])
        right_bottom = (bbox_int[2], bbox_int[3])
        cv2.rectangle(img, left_top, right_bottom, bbox_color, thickness)
        label_text = class_names[
            label] if class_names is not None else f'cls {label}'
        if len(bbox) > 4:
            label_text += f'|{bbox[-1]:.02f}'
        cv2.putText(img, label_text, (bbox_int[0], bbox_int[1] - 2),
                    cv2.FONT_HERSHEY_COMPLEX, font_scale, text_color)
    imwrite(img, outfp)

image_ext = ['.jpg', '.jpeg', '.webp', '.bmp', '.png']
video_ext = ['mp4', 'mov', 'avi', 'mkv']
def get_image_list(path):
    image_names = []
    for maindir, subdir, file_name_list in os.walk(path):
        for filename in file_name_list:
            apath = os.path.join(maindir, filename)
            ext = os.path.splitext(apath)[1]
            if ext in image_ext:
                image_names.append(apath)
    return image_names


def main():

    args = parse_args()
    cfg = Config.fromfile(args.config)
    imgname = args.imgname
    class_names = cfg.class_names

    engine, data_pipeline, device = prepare(cfg)


    data = dict(img_info=dict(filename=imgname), img_prefix=None)

    data = data_pipeline(data)
    data = collate([data], samples_per_gpu=1)
    if device != 'cpu':
        # scatter to specified GPU
        data = scatter(data, [device])[0]
    else:
        # just get the actual data from DataContainer
        data['img_metas'] = data['img_metas'][0].data
        data['img'] = data['img'][0].data


    result = engine.infer(data['img'], data['img_metas'])[0]

    plot_result(result, imgname, class_names)




def main_floder():
    args = parse_args()
    cfg = Config.fromfile(args.config)
    imgPath = args.imgname
    class_names = cfg.class_names

    engine, data_pipeline, device = prepare(cfg)

    files = get_image_list(imgPath)
    files.sort()
    total_time=0
    for imgname in files:
        st = time.time()  # 返回当前的

        data = dict(img_info=dict(filename=imgname), img_prefix=None)

        data = data_pipeline(data)
        data = collate([data], samples_per_gpu=1)
        if device != 'cpu':
            # scatter to specified GPU
            data = scatter(data, [device])[0]
        else:
            # just get the actual data from DataContainer
            data['img_metas'] = data['img_metas'][0].data
            data['img'] = data['img'][0].data

        ed = time.time()  # 返回当前的
        print("tinaface 图片预处理时间:%.3f秒" % (ed - st))

        result = engine.infer(data['img'], data['img_metas'])[0]
        ed1 = time.time()
        print("tinaface运行时间:%.3f秒" % (ed1 - ed))
        total_time += (ed1-st)

        plot_result(result, imgname, class_names,"./result/"+imgname.split("/")[-1])
        ed2 = time.time()
        print("tinaface运行+save时间:%.3f秒" % (ed2 - ed1))

        print("tinaface 预处理＋运行+save时间:%.3f秒" % (ed2 - st))
    t1 = total_time / len(files)
    fps = 1.0 / t1
    print("total time:%.3f秒" % t1)
    print("total time:%.3f秒" % fps)

if __name__ == '__main__':
    args = parse_args()
    imgPath = args.imgname

    ext = os.path.splitext(imgPath)[1]
    if ext in image_ext:
        main()
    else:
        main_floder()
