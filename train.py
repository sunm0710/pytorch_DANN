import torch
from torch.autograd import Variable
import numpy as np

import params
import utils

def train(feature_extractor, class_classifier, domain_classifier, class_criterion, domain_criterion,
          source_dataloader, target_dataloader, optimizer, epoch):
    """
    Execute target domain adaptation
    :param feature_extractor:
    :param class_classifier:
    :param domain_classifier:
    :param class_criterion:
    :param domain_criterion:
    :param source_dataloader:
    :param target_dataloader:
    :param optimizer:
    :return:
    """
    # setup models
    feature_extractor.train()
    class_classifier.train()
    domain_classifier.train()

    # steps
    start_steps = epoch * len(source_dataloader)
    total_steps = params.epochs * len(source_dataloader)

    for batch_idx, (sdata, tdata) in enumerate(zip(source_dataloader, target_dataloader)):
        # setup hyperparameters
        p = float(batch_idx + start_steps) / total_steps
        constant = 2. / (1. + np.exp(-10 * p)) - 1

        # prepare the data
        input1, label1 = sdata
        input2, label2 = tdata
        size = min((input1.shape[0], input2.shape[0]))
        input1, label1 = input1[0:size, :, :, :], label1[0:size]
        input2, label2 = input2[0:size, :, :, :], label2[0:size]
        if params.use_gpu:
            input1, label1 = Variable(input1.cuda()), Variable(label1.cuda())
            input2, label2 = Variable(input2.cuda()), Variable(label2.cuda())
        input1, label1 = Variable(input1), Variable(label1)
        input2, label2 = Variable(input2), Variable(label2)

        # setup optimizer
        optimizer = utils.optimizer_scheduler(optimizer, p)
        optimizer.zero_grad()

        # prepare domian labels
        if params.use_gpu:
            source_labels = Variable(torch.zeros((input1.size()[0])).type(torch.LongTensor).cuda())
            target_labels = Variable(torch.ones((input2.size()[0])).type(torch.LongTensor).cuda())
        else:
            source_labels = Variable(torch.zeros((input1.size()[0])).type(torch.LongTensor))
            target_labels = Variable(torch.ones((input2.size()[0])).type(torch.LongTensor))

        # compute the output of source domain and target domain
        src_feature = feature_extractor(input1)
        tgt_feature = feature_extractor(input2)

        # compute the class loss of src_feature
        class_preds = class_classifier(src_feature)
        class_loss = class_criterion(class_preds, label1)

        # compute the domain loss of src_feature and target_feature
        tgt_preds = domain_classifier(tgt_feature, constant)
        src_preds = domain_classifier(src_feature, constant)
        tgt_loss = domain_criterion(tgt_preds, target_labels)
        src_loss = domain_criterion(src_preds, source_labels)
        domain_loss = tgt_loss + src_loss

        loss = class_loss + domain_loss
        loss.backward()
        optimizer.step()

        # print loss
        if (batch_idx + 1) % 10 == 0:
            print('[{}/{} ({:.0f}%)]\tLoss: {:.6f}\tClass Loss: {:.6f}\tDomain Loss: {:.6f}'.format(
                batch_idx * len(input2), len(target_dataloader.dataset),
                100. * batch_idx / len(target_dataloader), loss.data[0], class_loss.data[0],
                domain_loss.data[0]
            ))

