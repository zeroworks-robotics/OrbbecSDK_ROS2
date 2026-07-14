# =============================================================================
# multi_gmsl.launch.py
#
# Gemini 335Lg (GMSL) × 5대
#   RGBD_FRONT_SERIAL         →  rgbd_front         (Primary   — 마스터 클럭)
#   RGBD_FRONT_BOTTOM_SERIAL  →  rgbd_front_bottom  (Secondary — 슬레이브)
#   RGBD_RIGHT_SERIAL         →  rgbd_right         (Secondary — 슬레이브)
#   RGBD_LEFT_SERIAL          →  rgbd_left          (Secondary — 슬레이브)
#   RGBD_BACK_SERIAL          →  rgbd_back          (Secondary — 슬레이브)
#
# 시리얼 번호는 환경변수에서 읽어오며, 환경변수가 없으면 아래 기본값을 사용한다.
# 카메라 이름(=ROS 네임스페이스/토픽 접두어)과 환경변수 이름을 통일한다.
#
# noise_removal_filter:
#   전체 카메라 hardware(ASIC) 노이즈 리무버 사용 — CPU 부하 최소화
#   (이전 버전의 cam02 software 비교 설정은 제거)
# =============================================================================
import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node

# ── 카메라 정의 ──
# (camera_name, env_var, default_serial, sync_mode)
#   camera_name : ROS 네임스페이스 / 토픽 접두어
#   env_var     : 시리얼 번호를 읽어올 환경변수 이름
CAMERAS = [
    ('rgbd_front',        'RGBD_FRONT_SERIAL',        'CPB33630009R', 'primary'),
    ('rgbd_front_bottom', 'RGBD_FRONT_BOTTOM_SERIAL', 'CPB33630000S', 'secondary'),
    ('rgbd_right',        'RGBD_RIGHT_SERIAL',        'CPB9463000AV', 'secondary'),
    ('rgbd_left',         'RGBD_LEFT_SERIAL',         'CPB9463000YD', 'secondary'),
    ('rgbd_back',         'RGBD_BACK_SERIAL',         'CPB9463000FX', 'secondary'),
]

DELAY_CAM2 = 5.0
STAGGER_STEP = 3.0
# secondary 카메라 순차 기동 딜레이 (primary 기준)
SECONDARY_DELAYS = [DELAY_CAM2 + STAGGER_STEP * i for i in range(4)]


def generate_launch_description():
    pkg_dir     = get_package_share_directory('orbbec_camera')
    launch_file = os.path.join(pkg_dir, 'launch', 'gemini_330_series.launch.py')

    # 시리얼 번호는 환경변수에서 읽고, 없으면 기본값 사용.
    # 런치 인자로도 오버라이드 가능하도록 DeclareLaunchArgument 로 노출.
    args = [
        DeclareLaunchArgument(
            camera_name,
            default_value=os.environ.get(env_var, default_serial),
            description=f'{camera_name} 335Lg ({sync_mode}) 시리얼 번호 '
                        f'(환경변수 {env_var})',
        )
        for camera_name, env_var, default_serial, sync_mode in CAMERAS
    ]

    common = {
        'depth_width':                '640',
        'depth_height':               '480',
        'depth_fps':                  '30',
        'color_format':               'YUYV',
        'color_width':                '640',
        'color_height':               '480',
        'color_fps':                  '30',
        'ir_width':                   '640',
        'ir_height':                  '480',
        'ir_fps':                     '30',
        'enable_depth':               'true',
        'enable_color':               'true',
        'enable_left_ir':             'false',
        'enable_right_ir':            'false',
        'enable_point_cloud':         'true',
        'enable_colored_point_cloud': 'false',
        'color_qos':                  'sensor_data',
        'depth_qos':                  'sensor_data',
        'color_camera_info_qos':      'default',
        'depth_camera_info_qos':      'default',
        'log_level':                  'none',
        'device_num':                 '5',
    }

    def make_tf(name, z, frame_id, child_frame_id):
        return Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name=name,
            arguments=[
                '--x', '0.0', '--y', '0.0', '--z', str(z),
                '--roll', '0.0', '--pitch', '0.0', '--yaw', '0.0',
                '--frame-id', frame_id,
                '--child-frame-id', child_frame_id,
            ],
            output='screen',
        )

    # ── 카메라 그룹 생성 헬퍼 ──
    # 전체 카메라 하드웨어 노이즈 리무버로 통일
    def make_camera_group(camera_name, sync_mode):
        return GroupAction([
            LogInfo(msg=f'[{camera_name.upper()}] 335Lg ({sync_mode}) 기동'),
            LogInfo(msg='       noise_removal=hardware'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(launch_file),
                launch_arguments={
                    **common,
                    'camera_name':                          camera_name,
                    'serial_number':                        LaunchConfiguration(camera_name),
                    'sync_mode':                            sync_mode,
                    'enable_hardware_noise_removal_filter': 'true',
                    'enable_noise_removal_filter':          'false',
                }.items(),
            ),
        ])

    # primary 는 즉시 기동
    primary_name, _, _, primary_sync = CAMERAS[0]
    cameras = [make_camera_group(primary_name, primary_sync)]

    # secondary 는 순차적으로 딜레이 기동
    for (camera_name, _, _, sync_mode), delay in zip(CAMERAS[1:], SECONDARY_DELAYS):
        cameras.append(
            TimerAction(period=delay,
                        actions=[make_camera_group(camera_name, sync_mode)])
        )

    delay_msg = ' / '.join(f'+{d}s' for d in SECONDARY_DELAYS)

    return LaunchDescription([
        *args,
        LogInfo(msg='===== multi_gmsl.launch.py 시작: 335Lg × 5 (GMSL) HW Sync ====='),
        LogInfo(msg=f'Primary 즉시 → Secondary {delay_msg} 순차 기동'),
        LogInfo(msg='sync_mode: primary / secondary x4'),
        LogInfo(msg='noise_removal: 전체 hardware (ASIC)'),
        LogInfo(msg='cameras: rgbd_front / rgbd_front_bottom / rgbd_right / '
                    'rgbd_left / rgbd_back'),
        *cameras,
    ])
