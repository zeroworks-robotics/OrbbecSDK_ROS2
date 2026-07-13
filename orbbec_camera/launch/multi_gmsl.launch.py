# =============================================================================
# gmsl_335lg.launch.py
#
# Gemini 335Lg (GMSL) × 5대
#   CPB33630009R  →  camera_01  (Primary   — 마스터 클럭)
#   CPB33630000S  →  camera_02  (Secondary — 슬레이브)
#   CPB9463000AV  →  camera_03  (Secondary — 슬레이브)
#   CPB9463000YD  →  camera_04  (Secondary — 슬레이브)
#   CPB9463000FX  →  camera_05  (Secondary — 슬레이브)
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

DEFAULT_SERIAL_01 = 'CPB33630009R'   # primary
DEFAULT_SERIAL_02 = 'CPB33630000S'   # secondary
DEFAULT_SERIAL_03 = 'CPB9463000AV'   # secondary
DEFAULT_SERIAL_04 = 'CPB9463000YD'   # secondary
DEFAULT_SERIAL_05 = 'CPB9463000FX'   # secondary

DELAY_CAM2 = 5.0
STAGGER_STEP = 3.0
DELAY_CAM3 = DELAY_CAM2 + STAGGER_STEP
DELAY_CAM4 = DELAY_CAM2 + STAGGER_STEP * 2
DELAY_CAM5 = DELAY_CAM2 + STAGGER_STEP * 3


def generate_launch_description():
    pkg_dir     = get_package_share_directory('orbbec_camera')
    launch_file = os.path.join(pkg_dir, 'launch', 'gemini_330_series.launch.py')

    args = [
        DeclareLaunchArgument('camera_01', default_value=DEFAULT_SERIAL_01,
            description='335Lg Primary 시리얼 번호'),
        DeclareLaunchArgument('camera_02', default_value=DEFAULT_SERIAL_02,
            description='335Lg Secondary #1 시리얼 번호'),
        DeclareLaunchArgument('camera_03', default_value=DEFAULT_SERIAL_03,
            description='335Lg Secondary #2 시리얼 번호'),
        DeclareLaunchArgument('camera_04', default_value=DEFAULT_SERIAL_04,
            description='335Lg Secondary #3 시리얼 번호'),
        DeclareLaunchArgument('camera_05', default_value=DEFAULT_SERIAL_05,
            description='335Lg Secondary #4 시리얼 번호'),
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

    # tf_cam1 = make_tf('tf_base_to_cam01', 0.00, 'base_link', 'camera_01_link')
    # tf_cam2 = make_tf('tf_base_to_cam02', 0.03, 'base_link', 'camera_02_link')
    # tf_cam3 = make_tf('tf_base_to_cam03', 0.06, 'base_link', 'camera_03_link')
    # tf_cam4 = make_tf('tf_base_to_cam04', 0.09, 'base_link', 'camera_04_link')
    # tf_cam5 = make_tf('tf_base_to_cam05', 0.12, 'base_link', 'camera_05_link')

    # ── 카메라 그룹 생성 헬퍼 ──
    # 전체 카메라 하드웨어 노이즈 리무버로 통일
    def make_camera_group(camera_name, serial_arg, sync_mode):
        return GroupAction([
            LogInfo(msg=f'[{camera_name.upper()}] 335Lg ({sync_mode}) 기동'),
            LogInfo(msg='       noise_removal=hardware'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(launch_file),
                launch_arguments={
                    **common,
                    'camera_name':                          camera_name,
                    'serial_number':                        LaunchConfiguration(serial_arg),
                    'sync_mode':                            sync_mode,
                    'enable_hardware_noise_removal_filter': 'true',
                    'enable_noise_removal_filter':          'false',
                }.items(),
            ),
        ])

    cam1 = make_camera_group('camera_01', 'camera_01', 'primary')

    cam2 = TimerAction(period=DELAY_CAM2,
        actions=[make_camera_group('camera_02', 'camera_02', 'secondary')])
    cam3 = TimerAction(period=DELAY_CAM3,
        actions=[make_camera_group('camera_03', 'camera_03', 'secondary')])
    cam4 = TimerAction(period=DELAY_CAM4,
        actions=[make_camera_group('camera_04', 'camera_04', 'secondary')])
    cam5 = TimerAction(period=DELAY_CAM5,
        actions=[make_camera_group('camera_05', 'camera_05', 'secondary')])

    return LaunchDescription([
        *args,
        LogInfo(msg='===== gmsl_335lg.launch.py 시작: 335Lg × 5 (GMSL) HW Sync ====='),
        LogInfo(msg=f'Primary 즉시 → Secondary +{DELAY_CAM2}s / +{DELAY_CAM3}s / '
                    f'+{DELAY_CAM4}s / +{DELAY_CAM5}s 순차 기동'),
        LogInfo(msg='sync_mode: primary / secondary x4'),
        LogInfo(msg='noise_removal: 전체 hardware (ASIC)'),
        LogInfo(msg='TF: base_link → camera_01~05_link (z: 0.00~0.12, step 0.03)'),
        cam1, cam2, cam3, cam4, cam5,
    ])