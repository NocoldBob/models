#!/usr/bin/env python
# coding: utf-8
import logging
import random

import numpy as np
import pickle

# disable gpu training for this example
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import paddle
import paddle.fluid as fluid

from config import parse_args
from reader import CriteoDataset
from network import DCN

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('fluid')
logger.setLevel(logging.INFO)


def infer():
    args = parse_args()
    print(args)

    place = fluid.CPUPlace()
    inference_scope = fluid.Scope()

    test_files = [
        os.path.join(args.test_valid_data_dir, fname)
        for fname in next(os.walk(args.test_valid_data_dir))[2]
    ]

    test_files = random.sample(test_files, int(len(test_files) * 0.5))
    print('test files num {}'.format(len(test_files)))

    criteo_dataset = CriteoDataset()
    criteo_dataset.setup()
    test_reader = criteo_dataset.test_reader(test_files, args.batch_size, 100)

    startup_program = fluid.framework.Program()
    test_program = fluid.framework.Program()
    cur_model_path = args.model_output_dir + '/epoch_' + args.test_epoch

    with fluid.scope_guard(inference_scope):
        with fluid.framework.program_guard(test_program, startup_program):
            dcn_model = DCN(args.cross_num, args.dnn_hidden_units,
                            args.l2_reg_cross, args.use_bn)
            dcn_model.build_network(is_test=True)

            exe = fluid.Executor(place)
            feeder = fluid.DataFeeder(
                feed_list=dcn_model.data_list, place=place)
            fluid.io.load_persistables(
                executor=exe,
                dirname=cur_model_path,
                main_program=fluid.default_main_program())

            auc_states_names = ['_generated_var_2', '_generated_var_3']
            for name in auc_states_names:
                param = inference_scope.var(name).get_tensor()
                param_array = np.zeros(param._get_dims()).astype("int64")
                param.set(param_array, place)

            loss_all = 0
            num_ins = 0
            for batch_id, data_test in enumerate(test_reader()):
                loss_val, auc_val = exe.run(test_program,
                                            feed=feeder.feed(data_test),
                                            fetch_list=[
                                                dcn_model.avg_logloss.name,
                                                dcn_model.auc_var.name
                                            ])
                # num_ins += len(data_test)
                num_ins += 1
                loss_all += loss_val
                logger.info('TEST --> batch: {} loss: {} auc_val: {}'.format(
                    batch_id, loss_all / num_ins, auc_val))

            print(
                'The last log info is the total Logloss and AUC for all test data. '
            )


if __name__ == '__main__':
    infer()
