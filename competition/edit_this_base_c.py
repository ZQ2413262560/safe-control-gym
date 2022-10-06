"""Write your control strategy.

Then run:

    $ python3 getting_started.py --overrides ./getting_started.yaml

Tips:
    Search for strings `INSTRUCTIONS:` and `REPLACE THIS (START)` in this file.

    Change the code between the 4 blocks starting with
        #########################
        # REPLACE THIS (START) ##
        #########################
    and ending with
        #########################
        # REPLACE THIS (END) ####
        #########################
    with your own code.

    They are in methods:
        1) __init__
        2) cmdFirmware
        3) interStepLearn (optional)
        4) interEpisodeLearn (optional)

"""
from bdb import set_trace
from tkinter import Y
import numpy as np
import time
from collections import deque

try:
    from competition_utils import Command, PIDController, timing_step, timing_ep, plot_trajectory, draw_trajectory
except ImportError:
    # Test import.
    from .competition_utils import Command, PIDController, timing_step, timing_ep, plot_trajectory, draw_trajectory
from gym.spaces import Box
from slam import SLAM
class Controller():
    """Template controller class.

    """

    def __init__(self,
                 initial_obs,
                 initial_info,
                 use_firmware: bool = False,
                 buffer_size: int = 100,
                 verbose: bool = False
                 ):
        """Initialization of the controller.

        INSTRUCTIONS:
            The controller's constructor has access the initial state `initial_obs` and the a priori infromation
            contained in dictionary `initial_info`. Use this method to initialize constants, counters, pre-plan
            trajectories, etc.

        Args:
            initial_obs (ndarray): The initial observation of the quadrotor's state
                [x, x_dot, y, y_dot, z, z_dot, phi, theta, psi, p, q, r].
            initial_info (dict): The a priori information as a dictionary with keys
                'symbolic_model', 'nominal_physical_parameters', 'nominal_gates_pos_and_type', etc.
            use_firmware (bool, optional): Choice between the on-board controll in `pycffirmware`
                or simplified software-only alternative.
            buffer_size (int, optional): Size of the data buffers used in method `learn()`.
            verbose (bool, optional): Turn on and off additional printouts and plots.

        """
        # Save environment and conrol parameters.
        self.CTRL_TIMESTEP = initial_info["ctrl_timestep"]
        self.CTRL_FREQ = initial_info["ctrl_freq"]


        # when level 1 this will be changed
        # [-0.9660992341982342, 0, -2.906546142854587, 0, 0.04960550660033104, 0, 0.02840173653255687, -0.05744735611733429, 0.07373743557600966, 0, 0, 0]
        # [-0.96609923  0.         -2.90654614  0.          0.04960551  0.        0.02840174           -0.05744736           0.07373744   0.      0.    0.        ]
        self.initial_obs = initial_obs

        self.VERBOSE = verbose
        self.BUFFER_SIZE = buffer_size

        # Store a priori scenario information.

        # when level 2 this will be changed
        # x y z r p y 
        # initial is [[0.5, -2.5, 0, 0, 0, -1.57, 0], [2, -1.5, 0, 0, 0, 0, 1], [0, 0.2, 0, 0, 0, 1.57, 1], [-0.5, 1.5, 0, 0, 0, 0, 0]]
        #  when target gate show in horizon , be like "Current target gate position: [0.6143489615604684, -2.634075935292277, 1.0, 0.0, 0.0, -1.6783756661588305]"
        self.NOMINAL_GATES = initial_info["nominal_gates_pos_and_type"]
        
        # when level 2 this will be changed
        # x y z r p y 
        # [[1.5, -2.5, 0, 0, 0, 0], [0.5, -1, 0, 0, 0, 0], [1.5, 0, 0, 0, 0, 0], [-1, 0, 0, 0, 0, 0]]  
        self.NOMINAL_OBSTACLES = initial_info["nominal_obstacles_pos"] 
        
        # Check for pycffirmware.
        if use_firmware:
            self.ctrl = None
        else:
            # Initialize a simple PID Controller ror debugging and test
            # Do NOT use for the IROS 2022 competition. 
            self.ctrl = PIDController()
            # Save additonal environment parameters.
            self.KF = initial_info["quadrotor_kf"]



        #########################
        # REPLACE THIS (START) ##
        #########################
        import torch
        torch.manual_seed(101)
        np.random.seed(101)
        self.net_work_freq=0.5     #  time gap  1  1s/次  0.5s/次   0.2m  400episode 

        # state-based 
        self.mass=initial_info['nominal_physical_parameters']['quadrotor_mass']
        self.global_state_dim = 9
        self.local_state_dim=[5,23,23]

        self.current_all_state=[np.zeros(self.global_state_dim),np.zeros(self.local_state_dim)]
        self.last_all_state=[np.zeros(self.global_state_dim),np.zeros(self.local_state_dim)]
        
        self.m_slam = SLAM()
        self.m_slam.reset_occ_map()

        # action    
        action_dim = 3
        max_action=2
        min_action=max_action * (-1)
        self.action_space=Box(np.array([min_action,min_action,min_action],dtype=np.float64),np.array([max_action,max_action,max_action],dtype=np.float64))
        self.action_space.seed(1)
        self.current_action=np.zeros(action_dim)
        self.last_action=np.zeros(action_dim)
        # network
        kwargs = {
            "state_dim": self.global_state_dim,
            "action_dim": action_dim,
            "max_action": max_action,
            "rew_discount": 0.99,
            "tau":0.005,
            "policy_noise": 0.2 * max_action,
            "noise_clip": 0.5 * max_action,
            "policy_freq": 2,
        }
        from safetyplusplus_folder import safetyplusplus,replay_buffer,unconstrained
        # td3 policy
        self.policy = unconstrained.TD3(**kwargs)
        local_state_shape=[5,23,23]
        self.replay_buffer = replay_buffer.IrosReplayBuffer(self.global_state_dim,local_state_shape,action_dim)

        # env-based variable
        self.episode_reward = 0
        self.episode_cost = 0
        self.episode_iteration=-1
        self.pass_time = 1e6
        self.end_add_buffer_iteration=1e6
        self.next_infer_iteration=1e6
        self.go_back=False
        self.pass_bool=False
        self.agent_type='passing'
        self.arrival_iteration =1e6
        self.goal_pos=[initial_info['x_reference'][0],initial_info['x_reference'][2],initial_info['x_reference'][4]]
        self.one_step_reward = 0 
        
        
        # Reset counters and buffers.
        self.reset()
        self.interEpisodeReset()

        #########################
        # REPLACE THIS (END) ####
        #########################


    def get_state(self,obs,info):
        local_state = self.m_slam.generate_3obs_img(obs,name=self.episode_iteration,save=False)   

        # state info : mass(1) + obs_info(3) + goal_info(3) + pic_info     
        # x,y,z  3 
        current_x=obs[0]
        current_y=obs[2]
        current_z=obs[4]

        if info !={}:
            # goal [x,y,z]
            if info['current_target_gate_id'] == -1 :
                current_goal_pos = self.goal_pos
                current_target_gate_in_range= 0 
            else :
                # 1 or 0  1
                current_target_gate_in_range= 1 if info['current_target_gate_in_range'] == True else 0
                # [x,y,z,r] exactly if current_target_gate_in_range==1 else [x,y,z,y] noisy  (r,p is zero ,ignored )
                current_target_gate_pos = info['current_target_gate_pos']
                if current_target_gate_pos[2]==0: #  means that  current_target_gate_in_range is False, add default height.
                    current_target_gate_pos[2]=1 if info['current_target_gate_type'] == 0 else 0.525
                current_target_gate_pos=np.array(current_target_gate_pos)[[0,1,2,5]]
                current_goal_pos=current_target_gate_pos[:3]
                  
        else :
            current_target_gate_in_range= 0 
            current_goal_pos=np.zeros(3)
        global_state=np.array([current_x,current_y,current_z,current_goal_pos[0]-current_x,current_goal_pos[1]-current_y,current_goal_pos[2]-current_z,
                               current_target_gate_in_range,info['current_target_gate_id'],self.mass])
        return [global_state,local_state]
           
    def cmdFirmware(self,time,obs,reward=None,done=None,info=None,exploration=True):
        """Pick command sent to the quadrotor through a Crazyswarm/Crazyradio-like interface.

        INSTRUCTIONS:
            Re-implement this method to return the target position, velocity, acceleration, attitude, and attitude rates to be sent
            from Crazyswarm to the Crazyflie using, e.g., a `cmdFullState` call.

        Args:
            time (float): Episode's elapsed time, in seconds.
            obs (ndarray): The quadrotor's Vicon data [x, 0, y, 0, z, 0, phi, theta, psi, 0, 0, 0].
            reward (float, optional): The reward signal.
            done (bool, optional): Wether the episode has terminated.
            info (dict, optional): Current step information as a dictionary with keys
                'constraint_violation', 'current_target_gate_pos', etc.

        Returns:
            Command: selected type of command (takeOff, cmdFullState, etc., see Enum-like class `Command`).
            List: arguments for the type of command (see comments in class `Command`)

        """
        self.episode_iteration+=1
       
        if self.ctrl is not None:
            raise RuntimeError("[ERROR] Using method 'cmdFirmware' but Controller was created with 'use_firmware' = False.")

        #########################
        # REPLACE THIS (START) ##
        #########################
        self.m_slam.update_occ_map(info)
        


        # begin with take off 
        if self.episode_iteration == 0:
            height = 1
            duration = 1.5
            command_type = Command(2)  # Take-off.
            args = [height, duration]

        # using network to choose action
        elif self.episode_iteration >= 3 * self.CTRL_FREQ :
            
            if self.episode_iteration % (30*self.net_work_freq) ==0:
                # cmdFullState
                command_type =  Command(1)   # cmdFullState.
                all_state=self.get_state(obs,info)
                global_state=all_state[0]
                if self.interepisode_counter <= 10:
                    action= self.action_space.sample() 
                else:
                    action = self.policy.select_action(all_state, exploration=exploration)  # array  delta_x , delta_y, delta_z
                action /= 10
                self.current_all_state=all_state
                self.current_action=action
                # import pdb;pdb.set_trace()
                target_pos = global_state[[0,1,2]] + action
                target_vel = np.zeros(3)
                target_acc = np.zeros(3)
                target_yaw = 0.
                target_rpy_rates = np.zeros(3)
                args=[target_pos, target_vel, target_acc, target_yaw, target_rpy_rates]
                # other time do nothing
            else :
                command_type = Command(0)  # None.
                args = []
       
        else :
            command_type = Command(0)  # None.
            args = []

        #########################
        # REPLACE THIS (END) ####
        #########################
        
        return command_type, args

    # NOT need to re-implement
    def cmdSimOnly(self,
                   time,
                   obs,
                   reward=None,
                   done=None,
                   info=None
                   ):
        """PID per-propeller thrusts with a simplified, software-only PID quadrotor controller.

        INSTRUCTIONS:
            You do NOT need to re-implement this method for the IROS 2022 Safe Robot Learning competition.
            Only re-implement this method when `use_firmware` == False to return the target position and velocity.

        Args:
            time (float): Episode's elapsed time, in seconds.
            obs (ndarray): The quadrotor's state [x, x_dot, y, y_dot, z, z_dot, phi, theta, psi, p, q, r].
            reward (float, optional): The reward signal.
            done (bool, optional): Wether the episode has terminated.
            info (dict, optional): Current step information as a dictionary with keys
                'constraint_violation', 'current_target_gate_pos', etc.

        Returns:
            List: target position (len == 3).
            List: target velocity (len == 3).

        """
        if self.ctrl is None:
            raise RuntimeError("[ERROR] Attempting to use method 'cmdSimOnly' but Controller was created with 'use_firmware' = True.")

        self.iteration = int(time*self.CTRL_FREQ)

        #########################
        if self.iteration < len(self.ref_x):
            target_p = np.array([self.ref_x[self.iteration], self.ref_y[self.iteration], self.ref_z[self.iteration]])
        else:
            target_p = np.array([self.ref_x[-1], self.ref_y[-1], self.ref_z[-1]])
        target_v = np.zeros(3)
        #########################

        return target_p, target_v

    @timing_step
    def interStepLearn(self,args,obs,reward,done,info):
        """Learning and controller updates called between control steps.

        INSTRUCTIONS:
            Use the historically collected information in the five data buffers of actions, observations,
            rewards, done flags, and information dictionaries to learn, adapt, and/or re-plan.

        Args:
            action (List): Most recent applied action.
            obs (List): Most recent observation of the quadrotor state.
            reward (float): Most recent reward.
            done (bool): Most recent done flag.
            info (dict): Most recent information dictionary.

        """
        self.interstep_counter += 1
        reward=0
        #########################
        # REPLACE THIS (START) ##
        #########################

        # add experience when use network to decide
        if  self.episode_iteration == 3 * self.CTRL_FREQ:
            self.last_all_state=self.current_all_state
            self.last_action = self.current_action
            # import pdb;pdb.set_trace()

        if  self.episode_iteration> 3 * self.CTRL_FREQ   :
            if self.episode_iteration % (30*self.net_work_freq) ==0:
                last_pos= self.last_all_state[0][[0,1,2]]
                current_pos=self.current_all_state[0][[0,1,2]]

                last2goal_vector= self.last_all_state[0][[3,4,5]]
                last2cur_vector=current_pos-last_pos
                cur2goal_vector=self.current_all_state[0][[3,4,5]]

                std_last2goal_vector=last2goal_vector/(min(abs(last2goal_vector)))
                std_last2goal_vector=np.array([max(min(_,1.),-1.) for _ in std_last2goal_vector])

                std_last2cur_vector=last2cur_vector/(min(abs(last2cur_vector)))
                std_last2cur_vector=np.array([max(min(_,1.),-1.) for _ in std_last2cur_vector])
               
                cur2goal_dis=sum(cur2goal_vector * cur2goal_vector)
                last2goal_dis=sum(last2goal_vector * last2goal_vector)
                # import pdb;pdb.set_trace()

                # 对于跨过门动作 给一个大的奖励
                if self.last_all_state[0][-2] == self.current_all_state[0][-2]:
                        reward =( last2goal_dis - cur2goal_dis ) * 20
                else:
                    reward = 10
                # the direction is right
                # if int(sum(last2goal_vector * last2cur_vector))==3:
                #     reward = sum((current_pos-last_pos) * last2goal_vector) * 10
                # else:
                #     reward_raw=sum((current_pos-last_pos) * last2goal_vector) * 10
                #     reward = reward_raw if reward_raw<0 else -reward_raw

                # cross the gate
                if info['current_target_gate_id']!=self.target_gate_id :
                    print(f"STEP{self.episode_iteration} , step gate{self.target_gate_id}")
                    reward += 100
                if info['at_goal_position']:
                    reward += 100
                if info['constraint_violation'] :
                    reward -= 10
                if info["collision"][1] :
                    reward -= 10
            # cmdFullState
                if self.episode_iteration % 900 ==0  :
                    print(f"Step{self.episode_iteration} add buffer:\n last_pos:{last_pos} aim vector: {last2goal_vector} ")
                    print(f"action_infer: {self.last_action * 10}\t lastDis-CurDis:{( last2goal_dis - cur2goal_dis )}")
                    print(f"last2cur_pos_vector: {last2cur_vector } \t reward: {reward}")
                    print(f"target_gate_id:{info['current_target_gate_id']} ; pos: {info['current_target_gate_pos']}")
                    print("*********************************************")
                self.replay_buffer.add(self.last_all_state[0],self.last_all_state[1],self.last_action * 10 ,self.current_all_state[0],self.current_all_state[1],reward,done)
                # import pdb;pdb.set_trace()
                self.episode_reward+=reward
                # self.one_step_reward=reward
                # ready for next update
                self.last_all_state=self.current_all_state
                self.last_action=self.current_action
                self.target_gate_id= info['current_target_gate_id']
                
            else :
                pass
                # self.one_step_reward+=reward

            # network do one step , train 100 steps.
            if self.interepisode_counter >= 20 and self.episode_iteration % (15*self.net_work_freq) ==0:
                begin_time=time.time()
                self.policy.train(self.replay_buffer,batch_size=256,train_nums=int(30))
                if self.episode_iteration % 900 ==0  :
                    print(f"episode: {self.interepisode_counter},training using {time.time()-begin_time} s")
           
        

        #########################
        # REPLACE THIS (END) ####
        #########################

    @timing_ep
    def interEpisodeLearn(self,file_name):
        """Learning and controller updates called between episodes.

        INSTRUCTIONS:
            Use the historically collected information in the five data buffers of actions, observations,
            rewards, done flags, and information dictionaries to learn, adapt, and/or re-plan.

        """
        self.interepisode_counter += 1
        
        #########################
        # REPLACE THIS (START) ##
        #########################

        # if self.interepisode_counter >= 20 :
        #     self.policy.train(self.replay_buffer,batch_size=256,train_nums=(30 /self.net_work_freq ))

        if self.interepisode_counter >= 15 and self.interepisode_counter % 50 == 0 :
            self.policy.save(filename=f"{file_name}/{self.interepisode_counter}")
        return self.episode_reward
        #########################
        # REPLACE THIS (END) ####
        #########################

    def reset(self):
        """Initialize/reset data buffers and counters.

        Called once in __init__().

        """
        # Data buffers.
        # self.action_buffer = deque([], maxlen=self.BUFFER_SIZE)
        # self.obs_buffer = deque([], maxlen=self.BUFFER_SIZE)
        # self.reward_buffer = deque([], maxlen=self.BUFFER_SIZE)
        # self.done_buffer = deque([], maxlen=self.BUFFER_SIZE)
        # self.info_buffer = deque([], maxlen=self.BUFFER_SIZE)

        # Counters.
        self.interstep_counter = 0
        self.interepisode_counter = 0

    def interEpisodeReset(self):
        """Initialize/reset learning timing variables.

        Called between episodes in `getting_started.py`.

        """
        # Timing stats variables.
        self.interstep_learning_time = 0
        self.interstep_learning_occurrences = 0
        self.interepisode_learning_time = 0

        self.episode_reward = 0
        self.episode_cost = 0

        self.episode_iteration=-1
        self.pass_time = 1e6
        # env-based variable
        self.go_back=False
        self.pass_bool=False
        self.agent_type='passing'
        self.arrival_iteration =1e6
        self.one_step_reward = 0 
        self.next_infer_iteration=1e6
        self.end_add_buffer_iteration=1e6
        self.target_gate_id=0
        self.m_slam.reset_occ_map()
        self.current_all_state=[np.zeros(self.global_state_dim),np.zeros(self.local_state_dim)]
        self.last_all_state=[np.zeros(self.global_state_dim),np.zeros(self.local_state_dim)]