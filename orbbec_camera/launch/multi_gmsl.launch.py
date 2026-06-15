# =============================================================================
# gmsl_335lg.launch.py
#
# Gemini 335Lg (GMSL) × 2대
#   CPB33630009R  →  camera_01  (Primary  — 마스터 클럭)
#   CPB33630000S  →  camera_02  (Secondary — 슬레이브)
#
# TF 구성 (임시):
#   base_link → camera_01_link  (0, 0, 0)
#   base_link → camera_02_link  (0, 0, 0.03)
#
# 하드웨어 동기화:
#   sync_mode primary  → 내부 클럭으로 트리거 신호 생성 (cam01)
#   sync_mode secondary → primary 트리거에 맞춰 노출 시작  (cam02)
#   두 카메라가 동일 타임스탬프로 publish → camera_01 지연(~1.8s) 해소 목적
#
#   ※ GMSL 케이블을 통해 하드웨어 sync 신호가 연결되어 있어야 함
#   ※ 신호 미연결 시 secondary 가 프레임을 수신하지 못할 수 있음
#      → 그 경우 DELAY_CAM2 를 늘리거나 free_run 으로 롤백
#
# noise_removal_filter:
#   cam01: hardware (ASIC 처리) — CPU 부하 낮음
#   cam02: software (CPU 처리)  — CPU 부하 높음  ← 의도적 비교 설정
#
# 사전 작업:
#   sudo pkill -9 -f orbbec; sudo pkill -9 -f component_container
#   sudo rm -f /tmp/orb_device_lock_* /dev/shm/orb_*
#
# GMSL 디바이스 확인:
#   v4l2-ctl --list-devices
#   ros2 run orbbec_camera list_devices_node
#
# 실행:
#   ros2 launch orbbec_camera gmsl_335lg.launch.py
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


DEFAULT_SERIAL_LEFT  = 'CPB33630009R'
DEFAULT_SERIAL_RIGHT = 'CPB33630000S'

# Secondary 기동 딜레이 — Primary 완전 초기화 후 secondary 연결
# 동기화 모드에서는 primary 가 먼저 올라와야 트리거 신호가 생성됨
# free_run 대비 +2s 여유 추가 (3.0 → 5.0)
DELAY_CAM2 = 5.0


def generate_launch_description():

    pkg_dir     = get_package_share_directory('orbbec_camera')
    launch_file = os.path.join(pkg_dir, 'launch', 'gemini_330_series.launch.py')

    args = [
        DeclareLaunchArgument('camera_01',
            default_value=DEFAULT_SERIAL_LEFT,
            description='335Lg Primary (Left) 시리얼 번호'),
        DeclareLaunchArgument('camera_02',
            default_value=DEFAULT_SERIAL_RIGHT,
            description='335Lg Secondary (Right) 시리얼 번호'),
    ]

    common = {
        'depth_width':                '640',
        'depth_height':               '480',
        'depth_fps':                  '30',
        'color_format':               'YUYV',
        'color_width':                '1280',
        'color_height':               '720',
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
        'device_num':                 '2',
        # sync_mode 는 각 카메라별로 다르게 설정 (common 에서 제외)
    }

    # ── TF: base_link → camera_01_link ──
    tf_cam1 = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_base_to_cam01',
        arguments=[
            '--x',     '0.0',
            '--y',     '0.0',
            '--z',     '0.0',
            '--roll',  '0.0',
            '--pitch', '0.0',
            '--yaw',   '0.0',
            '--frame-id',       'base_link',
            '--child-frame-id', 'camera_01_link',
        ],
        output='screen',
    )

    # ── TF: base_link → camera_02_link ──
    tf_cam2 = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_base_to_cam02',
        arguments=[
            '--x',     '0.0',
            '--y',     '0.0',
            '--z',     '0.03',
            '--roll',  '0.0',
            '--pitch', '0.0',
            '--yaw',   '0.0',
            '--frame-id',       'base_link',
            '--child-frame-id', 'camera_02_link',
        ],
        output='screen',
    )

    # ── CAM 1: Primary — 즉시 기동 ──
    # sync_mode=primary: 내부 클럭으로 트리거 신호를 생성하고
    # GMSL 라인을 통해 secondary 로 전달
    cam1 = GroupAction([
        LogInfo(msg='[CAM1] 335Lg Primary (GMSL) CPB33630009R 기동'),
        LogInfo(msg='       sync_mode=primary  |  noise_removal=hardware'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(launch_file),
            launch_arguments={
                **common,
                'camera_name':                          'camera_01',
                'serial_number':                        LaunchConfiguration('camera_01'),
                'sync_mode':                            'primary',
                'enable_hardware_noise_removal_filter': 'true',
                'enable_noise_removal_filter':          'false',
            }.items(),
        ),
    ])

    # ── CAM 2: Secondary — 5초 후 기동 ──
    # sync_mode=secondary: primary 트리거 수신 후 노출 시작
    # primary 보다 늦게 기동해야 트리거 신호를 정상 인식
    cam2 = TimerAction(
        period=DELAY_CAM2,
        actions=[GroupAction([
            LogInfo(msg='[CAM2] 335Lg Secondary (GMSL) CPB33630000S 기동'),
            LogInfo(msg='       sync_mode=secondary  |  noise_removal=software'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(launch_file),
                launch_arguments={
                    **common,
                    'camera_name':                          'camera_02',
                    'serial_number':                        LaunchConfiguration('camera_02'),
                    'sync_mode':                            'secondary',
                    'enable_hardware_noise_removal_filter': 'false',
                    'enable_noise_removal_filter':          'true',
                }.items(),
            ),
        ])],
    )

    return LaunchDescription([
        *args,
        LogInfo(msg='===== gmsl_335lg.launch.py 시작: 335Lg × 2 (GMSL) HW Sync ====='),
        LogInfo(msg='Primary 즉시 → Secondary +5s 순차 기동'),
        LogInfo(msg='sync_mode: primary / secondary'),
        LogInfo(msg='TF: base_link → camera_01_link (0,0,0) | camera_02_link (0,0,0.03)'),
        tf_cam1,
        tf_cam2,
        cam1,
        cam2,
    ])