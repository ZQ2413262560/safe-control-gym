"""Base script.

Run as:

    $ python3 getting_started.py --overrides ./getting_started.yaml

Look for instructions in `README.md` and `edit_this.py`.

"""
import time
import inspect
import numpy as np
import pybullet as p
import sys 
sys.path.append("..") 

from functools import partial
from rich.tree import Tree
from rich import print

from safe_control_gym.utils.configuration import ConfigFactory
from safe_control_gym.utils.registration import make
from safe_control_gym.utils.utils import sync
from safe_control_gym.envs.gym_pybullet_drones.Logger import Logger

try:
    from competition_utils import Command, thrusts
    from edit_this_base_c import Controller
except ImportError:
    # Test import.
    from .competition_utils import Command, thrusts
    from .edit_this_base_c import Controller

try:
    import pycffirmware
except ImportError:
    FIRMWARE_INSTALLED = False
else:
    FIRMWARE_INSTALLED = True
finally:
    print("Module 'cffirmware' available:", FIRMWARE_INSTALLED)

from safetyplusplus_folder.plus_logger import SafeLogger

file_name='0929_05_seed_step1_train60_maxAct2_Seed101_changeActTest'

# def eval(firmware_wrapper,env,eval_times):

#     CONFIG_FACTORY = ConfigFactory()
#     config2 = CONFIG_FACTORY.merge()
#     CTRL_FREQ = config2.quadrotor_config['ctrl_freq']
#     CTRL_DT = 1/CTRL_FREQ
#     obs, info = firmware_wrapper.reset()
#     vicon_obs = [obs[0], 0, obs[2], 0, obs[4], 0, obs[6], obs[7], obs[8], 0, 0, 0]
#         # obs = {x, x_dot, y, y_dot, z, z_dot, phi, theta, psi, p, q, r}.
#         # vicon_obs = {x, 0, y, 0, z, 0, phi, theta, psi, 0, 0, 0}.
#     ctrl = Controller(vicon_obs, info, config2.use_firmware, verbose=config2.verbose)

#     # Create a logger and counters
#     episodes_count = 1
#     cumulative_reward = 0
#     collisions_count = 0
#     collided_objects = set()
#     violations_count = 0
#     episode_start_iter = 0

#     num_of_gates = len(config2.quadrotor_config.gates)

#     ep_start = time.time()
#     first_ep_iteration = True
#     episode_cost=0

#     success_time=0
#     success_rate=0
#     avg_pass_gates=0
#     avg_cost=0
#     total_pass_gates=0
#     total_cost=0
#     for i in range(eval_times*CTRL_FREQ*env.EPISODE_LEN_SEC):

#         # Elapsed sim time.
#         curr_time = (i-episode_start_iter)*CTRL_DT

#         # Compute control input.
#         # if config.use_firmware:
#         vicon_obs = [obs[0], 0, obs[2], 0, obs[4], 0, obs[6], obs[7], obs[8], 0, 0, 0]
#             # obs = {x, x_dot, y, y_dot, z, z_dot, phi, theta, psi, p, q, r}.
#             # vicon_obs = {x, 0, y, 0, z, 0, phi, theta, psi, 0, 0, 0}.
#         if first_ep_iteration:
#             action = np.zeros(4)
#             reward = 0
#             done = False
#             info = {}
#             first_ep_iteration = False
#         command_type, args = ctrl.cmdFirmware(curr_time, vicon_obs, reward, done, info,False)

#         # Select interface. 
#         if command_type == Command.FULLSTATE:
#             firmware_wrapper.sendFullStateCmd(*args, curr_time)
#         elif command_type == Command.TAKEOFF:
#             firmware_wrapper.sendTakeoffCmd(*args)
#         elif command_type == Command.LAND:
#             firmware_wrapper.sendLandCmd(*args)
#         elif command_type == Command.STOP:
#             firmware_wrapper.sendStopCmd()
#         elif command_type == Command.GOTO:
#             firmware_wrapper.sendGotoCmd(*args)
#         elif command_type == Command.NOTIFYSETPOINTSTOP:
#             firmware_wrapper.notifySetpointStop()
#         elif command_type == Command.NONE:
#             pass
#         else:
#             raise ValueError("[ERROR] Invalid command_type.")

#         obs, reward, done, info, _ = firmware_wrapper.step(curr_time, action)

#         # Add up reward, collisions, violations.
#         cumulative_reward += reward
#         if info["collision"][1]:
#             collisions_count += 1
#             collided_objects.add(info["collision"][0])
#             episode_cost+=1
#         if 'constraint_values' in info and info['constraint_violation'] == True:
#             violations_count += 1
#             episode_cost+=1


#         # If an episode is complete, reset the environment.
#         if done:
#             pass_gate_num=info['current_target_gate_id'] if info['current_target_gate_id']!=-1 else num_of_gates
#             success_time= success_time + (1 if pass_gate_num==num_of_gates else 0)
#             total_pass_gates+=pass_gate_num
#             total_cost+=episode_cost
#             # Reset/update counters.
#             episodes_count += 1
#             if episodes_count > eval_times:
#                 break
#             episode_cost = 0
#             cumulative_reward = 0
#             collisions_count = 0
#             collided_objects = set()
#             violations_count = 0
#             ctrl.interEpisodeReset()
#             # Reset the environment.
#             if config.use_firmware:
#                 # Re-initialize firmware.
#                 new_initial_obs, _ = firmware_wrapper.reset()
#             else:
#                 new_initial_obs, _ = env.reset()
#             first_ep_iteration = True
            
#             episode_start_iter = i+1
#             ep_start = time.time()
    
#     # Close the environment and print timing statistics.
#     env.close()
#     avg_cost=total_cost / eval_times
#     avg_pass_gates = total_pass_gates / eval_times
#     success_rate = success_time / eval_times
#     return avg_pass_gates,success_rate,avg_cost


def run(test=False):
    """The main function creating, running, and closing an environment over N episodes.

    """

    # Start a timer.
    START = time.time()

    # Load configuration.
    CONFIG_FACTORY = ConfigFactory()
    config = CONFIG_FACTORY.merge()

    # Testing (without pycffirmware).
    if test:
        config['use_firmware'] = False
        config['verbose'] = False
        config.quadrotor_config['ctrl_freq'] = 60
        config.quadrotor_config['pyb_freq'] = 240
        config.quadrotor_config['gui'] = False

    # Check firmware configuration.
    if config.use_firmware and not FIRMWARE_INSTALLED:
        raise RuntimeError("[ERROR] Module 'cffirmware' not installed.")
    CTRL_FREQ = config.quadrotor_config['ctrl_freq']
    CTRL_DT = 1/CTRL_FREQ

    # Create environment.
    if config.use_firmware:
        FIRMWARE_FREQ = 500
        assert(config.quadrotor_config['pyb_freq'] % FIRMWARE_FREQ == 0), "pyb_freq must be a multiple of firmware freq"
        # The env.step is called at a firmware_freq rate, but this is not as intuitive to the end user, and so 
        # we abstract the difference. This allows ctrl_freq to be the rate at which the user sends ctrl signals, 
        # not the firmware. 
        config.quadrotor_config['ctrl_freq'] = FIRMWARE_FREQ
        env_func = partial(make, 'quadrotor', **config.quadrotor_config)
        firmware_wrapper = make('firmware',
                    env_func, FIRMWARE_FREQ, CTRL_FREQ
                    ) 
        obs, info = firmware_wrapper.reset()
        info['ctrl_timestep'] = CTRL_DT
        info['ctrl_freq'] = CTRL_FREQ
        env = firmware_wrapper.env
        
        
    else:
        env = make('quadrotor', **config.quadrotor_config)
        # Reset the environment, obtain the initial observations and info dictionary.
        obs, info = env.reset()
    
    # Create controller.
    vicon_obs = [obs[0], 0, obs[2], 0, obs[4], 0, obs[6], obs[7], obs[8], 0, 0, 0]
        # obs = {x, x_dot, y, y_dot, z, z_dot, phi, theta, psi, p, q, r}.
        # vicon_obs = {x, 0, y, 0, z, 0, phi, theta, psi, 0, 0, 0}.
    ctrl = Controller(vicon_obs, info, config.use_firmware, verbose=config.verbose)

    # Create a logger and counters
    logger = Logger(logging_freq_hz=CTRL_FREQ)
    episodes_count = 1
    cumulative_reward = 0
    collisions_count = 0
    collided_objects = set()
    violations_count = 0
    episode_start_iter = 0
    time_label_id = p.addUserDebugText("", textPosition=[0, 0, 1],physicsClientId=env.PYB_CLIENT)
    num_of_gates = len(config.quadrotor_config.gates)
    stats = []

    # Wait for keyboard input to start.
    # input("Press any key to start")

    # Initial printouts.
    if config.verbose:
        print('\tInitial observation [x, 0, y, 0, z, 0, phi, theta, psi, 0, 0, 0]: ' + str(obs))
        print('\tControl timestep: ' + str(info['ctrl_timestep']))
        print('\tControl frequency: ' + str(info['ctrl_freq']))
        print('\tMaximum episode duration: ' + str(info['episode_len_sec']))
        print('\tNominal quadrotor mass and inertia: ' + str(info['nominal_physical_parameters']))
        print('\tGates properties: ' + str(info['gate_dimensions']))
        print('\tObstacles properties: ' + str(info['obstacle_dimensions']))
        print('\tNominal gates positions [x, y, z, r, p, y, type]: ' + str(info['nominal_gates_pos_and_type']))
        print('\tNominal obstacles positions [x, y, z, r, p, y]: ' + str(info['nominal_obstacles_pos']))
        print('\tFinal target hover position [x, x_dot, y, y_dot, z, z_dot, phi, theta, psi, p, q, r]: ' + str(info['x_reference']))
        print('\tDistribution of the error on the initial state: ' + str(info['initial_state_randomization']))
        print('\tDistribution of the error on the inertial properties: ' + str(info['inertial_prop_randomization']))
        print('\tDistribution of the error on positions of gates and obstacles: ' + str(info['gates_and_obs_randomization']))
        print('\tDistribution of the disturbances: ' + str(info['disturbances']))
        print('\tA priori symbolic model:')
        print('\t\tState: ' + str(info['symbolic_model'].x_sym).strip('vertcat'))
        print('\t\tInput: ' + str(info['symbolic_model'].u_sym).strip('vertcat'))
        print('\t\tDynamics: ' + str(info['symbolic_model'].x_dot).strip('vertcat'))
        print('Input constraints lower bounds: ' + str(env.constraints.input_constraints[0].lower_bounds))
        print('Input constraints upper bounds: ' + str(env.constraints.input_constraints[0].upper_bounds))
        print('State constraints active dimensions: ' + str(config.quadrotor_config.constraints[1].active_dims))
        print('State constraints lower bounds: ' + str(env.constraints.state_constraints[0].lower_bounds))
        print('State constraints upper bounds: ' + str(env.constraints.state_constraints[0].upper_bounds))
        print('\tSymbolic constraints: ')
        for fun in info['symbolic_constraints']:
            print('\t' + str(inspect.getsource(fun)).strip('\n'))
    
    
    logger_plus = SafeLogger(exp_name=file_name, env_name="compitition", seed=0,
                                fieldnames=['EpRet', 'EpCost', 'CostRate','collision_num','vilation_num','target_gate'])   
    # Run an experiment.
    ep_start = time.time()
    first_ep_iteration = True
    episode_cost=0
    for i in range(config.num_episodes*CTRL_FREQ*env.EPISODE_LEN_SEC):

        # Step by keyboard input.
        # _ = input("Press any key to continue")

        # Elapsed sim time.
        curr_time = (i-episode_start_iter)*CTRL_DT

        # Print episode time in seconds on the GUI.
        time_label_id = p.addUserDebugText("Ep. time: {:.2f}s".format(curr_time),
                                           textPosition=[0, 0, 1.5],
                                           textColorRGB=[1, 0, 0],
                                           lifeTime=3*CTRL_DT,
                                           textSize=1.5,
                                           parentObjectUniqueId=0,
                                           parentLinkIndex=-1,
                                           replaceItemUniqueId=time_label_id,
                                           physicsClientId=env.PYB_CLIENT)

        # Compute control input.
        if config.use_firmware:
            vicon_obs = [obs[0], 0, obs[2], 0, obs[4], 0, obs[6], obs[7], obs[8], 0, 0, 0]
                # obs = {x, x_dot, y, y_dot, z, z_dot, phi, theta, psi, p, q, r}.
                # vicon_obs = {x, 0, y, 0, z, 0, phi, theta, psi, 0, 0, 0}.
            if first_ep_iteration:
                action = np.zeros(4)
                reward = 0
                done = False
                info = {}
                first_ep_iteration = False
            command_type, args = ctrl.cmdFirmware(curr_time, vicon_obs, reward, done, info,True)

            #  'action_space': Box([0.02816169 0.02816169 0.02816169 0.02816169], [0.14834145 0.14834145 0.14834145 0.14834145], (4,), float32)
            # pdb.set_trace()
            # Select interface. 
            if command_type == Command.FULLSTATE:
                # import pdb; pdb.set_trace()
                firmware_wrapper.sendFullStateCmd(*args, curr_time)
            elif command_type == Command.TAKEOFF:
                firmware_wrapper.sendTakeoffCmd(*args)
            elif command_type == Command.LAND:
                firmware_wrapper.sendLandCmd(*args)
            elif command_type == Command.STOP:
                firmware_wrapper.sendStopCmd()
            elif command_type == Command.GOTO:
                firmware_wrapper.sendGotoCmd(*args)
            elif command_type == Command.NOTIFYSETPOINTSTOP:
                firmware_wrapper.notifySetpointStop()
            elif command_type == Command.NONE:
                pass
            else:
                raise ValueError("[ERROR] Invalid command_type.")

            # action
            # Step the environment.
            # TODO reward is exactly?
           
            obs, reward, done, info, _ = firmware_wrapper.step(curr_time, action)
            #
        else:
            if first_ep_iteration:
                reward = 0
                done = False
                info = {}
                first_ep_iteration = False
            target_pos, target_vel = ctrl.cmdSimOnly(curr_time, obs, reward, done, info)
            action = thrusts(ctrl.ctrl, ctrl.CTRL_TIMESTEP, ctrl.KF, obs, target_pos, target_vel)
            obs, reward, done, info = env.step(action)

        # Update the controller internal state and models.
        ctrl.interStepLearn(args, obs, reward, done, info)

        # Add up reward, collisions, violations.

        # base (not used )
        cumulative_reward += reward
        if info["collision"][1]:
            collisions_count += 1
            collided_objects.add(info["collision"][0])
            episode_cost+=1
        if 'constraint_values' in info and info['constraint_violation'] == True:
            violations_count += 1
            episode_cost+=1

        # Printouts.
        if config.verbose and i%int(CTRL_FREQ/2) == 0:
            print('\n'+str(i)+'-th step.')
            print('\tApplied action: ' + str(action))
            print('\tObservation: ' + str(obs))
            print('\tReward: ' + str(reward) + ' (Cumulative: ' + str(cumulative_reward) +')')
            print('\tDone: ' + str(done))
            print('\tCurrent target gate ID: ' + str(info['current_target_gate_id']))
            print('\tCurrent target gate type: ' + str(info['current_target_gate_type']))
            print('\tCurrent target gate in range: ' + str(info['current_target_gate_in_range']))
            print('\tCurrent target gate position: ' + str(info['current_target_gate_pos']))
            print('\tAt goal position: ' + str(info['at_goal_position']))
            print('\tTask completed: ' + str(info['task_completed']))
            if 'constraint_values' in info:
                print('\tConstraints evaluations: ' + str(info['constraint_values']))
                print('\tConstraints violation: ' + str(bool(info['constraint_violation'])))
            print('\tCollision: ' + str(info["collision"]))
            print('\tTotal collisions: ' + str(collisions_count))
            print('\tCollided objects (history): ' + str(collided_objects))

        # Log data.
        pos = [obs[0],obs[2],obs[4]]
        rpy = [obs[6],obs[7],obs[8]]
        vel = [obs[1],obs[3],obs[5]]
        bf_rates = [obs[9],obs[10],obs[11]]
        logger.log(drone=0,
                   timestamp=i/CTRL_FREQ,
                   state=np.hstack([pos, np.zeros(4), rpy, vel, bf_rates, np.sqrt(action/env.KF)])
                   )

        # Synchronize the GUI.
        if config.quadrotor_config.gui:
            sync(i-episode_start_iter, ep_start, CTRL_DT)

        # If an episode is complete, reset the environment.
        if done:
            # Plot logging (comment as desired).
            # if not test:
                # logger.plot(comment="get_start-episode-"+str(episodes_count), autoclose=True)

            # CSV save.
            # logger.save_as_csv(comment="get_start-episode-"+str(episodes_count))

            # Update the controller internal state and models.
            episode_reward=ctrl.interEpisodeLearn(logger_plus.log_dir)

            # Append episode stats.
            # if info['current_target_gate_id'] == -1:
            #     gates_passed = num_of_gates
            # else:
            #     gates_passed = info['current_target_gate_id']
            # if config.quadrotor_config.done_on_collision and info["collision"][1]:
            #     termination = 'COLLISION'
            # elif config.quadrotor_config.done_on_completion and info['task_completed']:
            #     termination = 'TASK COMPLETION'
            # elif config.quadrotor_config.done_on_violation and info['constraint_violation']:
            #     termination = 'CONSTRAINT VIOLATION'
            # else:
            #     termination = 'MAX EPISODE DURATION'
            # if ctrl.interstep_learning_occurrences != 0:
            #     interstep_learning_avg = ctrl.interstep_learning_time/ctrl.interstep_learning_occurrences
            # else:
            #     interstep_learning_avg = ctrl.interstep_learning_time
            # episode_stats = [
            #     '[yellow]Flight time (s): '+str(curr_time),
            #     '[yellow]Reason for termination: '+termination,
            #     '[green]Gates passed: '+str(gates_passed),
            #     '[green]Total reward: '+str(cumulative_reward),
            #     '[red]Number of collisions: '+str(collisions_count),
            #     '[red]Number of constraint violations: '+str(violations_count),
            #     '[white]Total and average interstep learning time (s): '+str(ctrl.interstep_learning_time)+', '+str(interstep_learning_avg),
            #     '[white]Interepisode learning time (s): '+str(ctrl.interepisode_learning_time),
            #     ]
            # stats.append(episode_stats)

            # Create a new logger.
            logger = Logger(logging_freq_hz=CTRL_FREQ)

            print(f"Total T: {i + 1} Episode Num: {episodes_count}  Reward: {episode_reward:.3f} Cost: {episode_cost:.3f} violation: {violations_count:.3f}  collision:{collisions_count:.3f} gates_passed:{info['current_target_gate_id']},")
            print(f"at_goal_position : {info['at_goal_position']}  task_completed: {info['task_completed']}")
            logger_plus.update([episode_reward, episode_cost, episode_cost,collisions_count,violations_count,info['current_target_gate_id']], total_steps=i + 1)

            # Reset/update counters.
            episodes_count += 1
            if episodes_count > config.num_episodes:
                break
            episode_cost = 0
            cumulative_reward = 0
            collisions_count = 0
            collided_objects = set()
            violations_count = 0
            ctrl.interEpisodeReset()

            # Reset the environment.
            if config.use_firmware:
                # Re-initialize firmware.
                new_initial_obs, _ = firmware_wrapper.reset()
            else:
                new_initial_obs, _ = env.reset()
            first_ep_iteration = True

            if config.verbose:
                print(str(episodes_count)+'-th reset.')
                print('Reset obs' + str(new_initial_obs))
            
            # import pdb; pdb.set_trace()
            obs=new_initial_obs
            episode_start_iter = i+1
            ep_start = time.time()
        
        # if (i + 1) % 5000==0:
        #     import copy
        #     config2=copy.deepcopy(config)
        #     config2.quadrotor_config['gui'] = False
        #     eval_env_func = partial(make, 'quadrotor', **config2.quadrotor_config)
        #     eval_firmware_wrapper = make('firmware',
        #                 eval_env_func, FIRMWARE_FREQ, CTRL_FREQ
        #                 ) 
        #     eval_env = eval_firmware_wrapper.env
        #     avg_pass_gates,success_rate,avg_cost=eval(eval_firmware_wrapper,eval_env,5)

    # Close the environment and print timing statistics.
    env.close()
    elapsed_sec = time.time() - START
    print(str("\n{:d} iterations (@{:d}Hz) and {:d} episodes in {:.2f} sec, i.e. {:.2f} steps/sec for a {:.2f}x speedup.\n"
          .format(i,
                  env.CTRL_FREQ,
                  config.num_episodes,
                  elapsed_sec,
                  i/elapsed_sec,
                  (i*CTRL_DT)/elapsed_sec
                  )
          ))

    # Print episodes summary.
    # tree = Tree("Summary")
    # for idx, ep in enumerate(stats):
    #     ep_tree = tree.add('Episode ' + str(idx+1))
    #     for val in ep:
    #         ep_tree.add(val)
    # print('\n\n')
    # print(tree)
    # print('\n\n')

if __name__ == "__main__":
    run()
