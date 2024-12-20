import os
import pickle
import time
import warnings

import model
import numpy as np
import torch
from data_loader import data_provider
from utils.metrics import metric
from utils.tools import EarlyStopping, adjust_learning_rate, visual

warnings.filterwarnings("ignore")


class Trainer:
    def __init__(self, args):
        self.args = args
        self.device = torch.device("cpu")
        self.model = model.Model(self.args)

    def _get_data(self, flag):
        data_set, data_loader = data_provider(self.args, flag)
        return data_set, data_loader

    def vali(self, vali_data, vali_loader):
        total_loss = []
        for i, (batch_x, batch_y) in enumerate(vali_loader):
            # for this homework, we use torch for data loading only
            batch_x = batch_x.detach().cpu().numpy()
            batch_y = batch_y.detach().cpu().numpy()

            outputs, loss = self.model.forward_backward(batch_x, batch_y, forward_only=True)

            total_loss.append(loss)
        total_loss = np.average(total_loss)
        return total_loss

    def train(self, setting):
        train_data, train_loader = self._get_data(flag="train")
        vali_data, vali_loader = self._get_data(flag="val")
        test_data, test_loader = self._get_data(flag="test")

        path = os.path.join(self.args.checkpoints, setting)
        if not os.path.exists(path):
            os.makedirs(path)

        time_now = time.time()

        train_steps = len(train_loader)
        early_stopping = EarlyStopping(verbose=True)
        lr, wd = self.args.learning_rate, self.args.weight_decay

        for epoch in range(self.args.train_epochs):
            iter_count = 0
            train_loss = []

            epoch_time = time.time()
            for i, (batch_x, batch_y) in enumerate(train_loader):
                iter_count += 1
                # for this homework, we use torch for data loading only
                batch_x = batch_x.detach().cpu().numpy()
                batch_y = batch_y.detach().cpu().numpy()

                outputs, loss = self.model.forward_backward(batch_x, batch_y)
                self.model.update_weights(lr, wd)

                train_loss.append(loss)

                if (i + 1) % 100 == 0:
                    print(f"\titers: {i + 1}, epoch: {epoch + 1} | loss: {loss.item():.7f}")
                    speed = (time.time() - time_now) / iter_count
                    left_time = speed * ((self.args.train_epochs - epoch) * train_steps - i)
                    print(f"\tspeed: {speed:.4f}s/iter; left time: {left_time:.4f}s")
                    iter_count = 0
                    time_now = time.time()

            print(f"Epoch: {epoch + 1} cost time: {time.time() - epoch_time}")
            train_loss = np.average(train_loss)
            vali_loss = self.vali(vali_data, vali_loader)
            test_loss = self.vali(test_data, test_loader)

            print(f"Epoch: {epoch + 1}, Steps: {train_steps} | Train Loss: {train_loss:.7f} Vali Loss: {vali_loss:.7f} Test Loss: {test_loss:.7f}")
            early_stopping(vali_loss, self.model, path)
            if early_stopping.early_stop:
                print("Early stopping")
                break

            lr = adjust_learning_rate(epoch + 1, self.args)

        best_model_path = path + "/" + "checkpoint.pth"
        self.model.load_state_dict(pickle.load(open(best_model_path, "br")))

        return self.model

    def test(self, setting, test=0):
        test_data, test_loader = self._get_data(flag="test")
        if test:
            print("loading model")
            self.model.load_state_dict(pickle.load(
                open(os.path.join("./checkpoints/" + setting, "checkpoint.pth", "br"))))

        preds = []
        trues = []
        folder_path = "./test_results/" + setting + "/"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        for i, (batch_x, batch_y) in enumerate(test_loader):
            # for this homework, we use torch for data loading only
            batch_x = batch_x.detach().cpu().numpy()
            batch_y = batch_y.detach().cpu().numpy()

            outputs, loss = self.model.forward_backward(batch_x, batch_y, forward_only=True)

            pred = outputs
            true = batch_y

            preds.append(pred)
            trues.append(true)
            if i % 20 == 0:
                input = batch_x
                gt = np.concatenate((input[0, :, -1], true[0, :, -1]), axis=0)
                pd = np.concatenate((input[0, :, -1], pred[0, :, -1]), axis=0)
                visual(gt, pd, os.path.join(folder_path, str(i) + ".pdf"))

        preds = np.array(preds)
        trues = np.array(trues)
        print("test shape:", preds.shape, trues.shape)
        preds = preds.reshape(-1, preds.shape[-2], preds.shape[-1])
        trues = trues.reshape(-1, trues.shape[-2], trues.shape[-1])
        print("test shape:", preds.shape, trues.shape)

        # result save
        folder_path = "./results/" + setting + "/"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        mae, mse, rmse, mape, mspe = metric(preds, trues)
        print(f"mse:{mse}, mae:{mae}")
        f = open("result_long_term_forecast.txt", "a")
        f.write(setting + "  \n")
        f.write(f"mse:{mse}, mae:{mae}")
        f.write("\n")
        f.write("\n")
        f.close()

        np.save(folder_path + "metrics.npy", np.array([mae, mse, rmse, mape, mspe]))
        np.save(folder_path + "pred.npy", preds)
        np.save(folder_path + "true.npy", trues)

