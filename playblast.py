#!/usr/bin/env python
# coding=utf-8
'''
Author        : zhenghaoming
Date          : 2022-08-08 13:52:45
FilePath      : \XYY\playblast\playblast\playblast.py
version       : 
LastEditors   : zhenghaoming
LastEditTime  : 2022-08-29 10:21:27
'''
import os,sys,time,copy,traceback,subprocess,json

try:
    from PySide.QtGui import *
    from PySide.QtCore import *
except ImportError:
    from PySide2.QtGui import *
    from PySide2.QtCore import *
    from PySide2.QtWidgets import *

from shiboken2 import wrapInstance
from shiboken2 import getCppPointer
from functools import partial

import maya.OpenMayaUI as omui
import maya.api.OpenMaya as om
import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel

ddhud_path = r'\\172.22.5.10\software\XYYScript'

class PlayblastCustomPresets(object):

    HUD_MASKS_LABELS =["focal_length",
                    "author",
                    "file_name",
                    "frame",
                    "time_range",
                    "camera",
                    "company_name",
                    "fps",
                    "date",
                    "proj_name"]


    RESOLUTION_PRESETS = [
        #
        # Format:  ["preset_name", (width, height)],
        #

        ["HD 1080", (1920, 1080)],
        ["HD 720", (1280, 720)],
        ["HD 540", (960, 540)],
    ]



    @classmethod
    def parse_playblast_output_dir_path(self, dir_path):
        """
        User defined output directory {tags}. Logic should replace tag with a string.

        PLAYBLAST_OUTPUT_PATH_LOOKUP can be used to add {tag} to context menu.
        """
        # if "{my_tag}" in dir_path:
        #     dir_path = dir_path.replace("{my_tag}", "My Custom Value")

        return dir_path

    @classmethod
    def parse_playblast_output_filename(self, filename):
        """
        User defined output filenname {tags}. Logic should replace tag with a string.

        PLAYBLAST_OUTPUT_FILENAME_LOOKUP can be used to add {tag} to context menu.
        """
        # if "{my_tag}" in filename:
        #     filename = filename.replace("{my_tag}", "My Custom Value")

        return filename

class PlayblastUtils(object):
    PLUG_IN_NAME = "DDHUD.py"

    @classmethod
    def is_plugin_loaded(cls):
        return cmds.pluginInfo(cls.PLUG_IN_NAME, q=True, loaded=True)

    @classmethod
    def load_plugin(cls):
        if not cls.is_plugin_loaded():
            try:
                cmds.loadPlugin("%s/plugins/%s" % (ddhud_path,cls.PLUG_IN_NAME))
            except:
                om.MGlobal.displayError("Failed to load Playblast plug-in: {0}".format(cls.PLUG_IN_NAME))
                cmds.confirmDialog( t=u'警告', m=u'查询不到DDHUD插件\n请检查!!',icn='warning', b=['Yes'], db='Yes', ds='No' )
                return

        return True

    @classmethod
    def get_ffmpeg_path(cls,ddhud_path):
        return ('%s/ffmpeg/ffmpeg.exe' % ddhud_path)

    @classmethod
    def cameras_in_scene(cls, include_defaults=True, user_created_first=True):
        default_cameras = ["front", "persp", "side", "top"]

        cameras = cmds.listCameras()

        if include_defaults and user_created_first or not include_defaults:
            for name in default_cameras:
                cameras.remove(name)

            if user_created_first:
                for name in default_cameras:
                    cameras.append(name)

        return cameras

# 将maya的颜色滑杆转成控件，并且可以与qt关联
class playblastColorButton(QWidget):

    color_changed = Signal()


    def __init__(self, color=(1.0, 1.0, 1.0), parent=None):
        super(playblastColorButton, self).__init__(parent)

        self.setObjectName("playblastColorButton")

        self.create_control()

        self.set_size(300, 16)
        self.set_color(color)

    def create_control(self):
        window = cmds.window()
        color_slider_name = cmds.colorSliderGrp()

        self._color_slider_obj = omui.MQtUtil.findControl(color_slider_name)
        if self._color_slider_obj:
            self._color_slider_widget = wrapInstance(long(self._color_slider_obj), QWidget)

            main_layout = QVBoxLayout(self)
            main_layout.setObjectName("main_layout")
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.addWidget(self._color_slider_widget)

            # self._slider_widget = self._color_slider_widget.findChild(QWidget, "slider")
            # if self._slider_widget:
            #     self._slider_widget.hide()

            self._color_widget = self._color_slider_widget.findChild(QWidget, "port")

            cmds.colorSliderGrp(self.get_full_name(), e=True, changeCommand=partial(self.on_color_changed))


        cmds.deleteUI(window, window=True)

    def get_full_name(self):
            return omui.MQtUtil.fullName(long(self._color_slider_obj))

    def set_size(self, width, height):
        self._color_slider_widget.setFixedWidth(width)
        self._color_widget.setFixedHeight(height)

    def set_color(self, color):
        cmds.colorSliderGrp(self.get_full_name(), e=True, rgbValue=(color[0], color[1], color[2]))
        self.on_color_changed()

    def get_color(self):
        return cmds.colorSliderGrp(self.get_full_name(), q=True, rgbValue=True)

    def on_color_changed(self, *args):
        self.color_changed.emit()  # pylint: disable=E1101

# 网格布局预设
class playblastFormLayout(QGridLayout):

    def __init__(self, parent=None):
        super(playblastFormLayout, self).__init__(parent)

        self.setContentsMargins(0, 0, 0, 8)
        self.setColumnMinimumWidth(0, 30)
        self.setHorizontalSpacing(6)

    def addWidgetRow(self, row, label, widget):
        self.addWidget(QLabel(label), row, 0, Qt.AlignLeft)
        self.addWidget(widget, row, 1)

    def addLayoutRow(self, row, label, layout):
        self.addWidget(QLabel(label), row, 0, Qt.AlignLeft)
        self.addLayout(layout, row, 1)

# 设置窗口 可以供 maya window命令查询并且删除或者加载
class playblastWorkspaceControl(object):
    def __init__(self, name):
        self.name = name
        self.widget = None

    def create(self, label, widget, ui_script=None):

        cmds.workspaceControl(self.name, label=label)

        if ui_script:
            cmds.workspaceControl(self.name, e=True, uiScript=ui_script)

        self.add_widget_to_layout(widget)
        self.set_visible(True)
    
    def restore(self,widget):
        self.add_widget_to_layout(widget)

    def add_widget_to_layout(self,widget):
        if widget:
            self.widget = widget
            self.widget.setAttribute(Qt.WA_DontCreateNativeAncestors)

            workspace_control_ptr = long(omui.MQtUtil.findControl(self.name))
            widget_ptr = long(getCppPointer(self.widget)[0])

            omui.MQtUtil.addWidgetToMayaLayout(widget_ptr, workspace_control_ptr)

    def exists(self):
        return cmds.workspaceControl(self.name, q=True, exists=True)

    def is_visible(self):
        return cmds.workspaceControl(self.name, q=True, visible=True)

    def set_visible(self, visible):
        if visible:
            cmds.workspaceControl(self.name, e=True, restore=True)
        else:
            cmds.workspaceControl(self.name, e=True, visible=False)

    def set_label(self, label):
        cmds.workspaceControl(self.name, e=True, label=label)

    def is_floating(self):
        return cmds.workspaceControl(self.name, q=True, floating=True)

    def is_collapsed(self):
        return cmds.workspaceControl(self.name, q=True, collapse=True)

class ShotMask(object):

    @classmethod
    def createHUD(cls,ddhud_path):
        if not PlayblastUtils.load_plugin():
            return

        if not cmds.objExists('ddhud_grp'):
            cmds.group(em=True,w=True,n='ddhud_grp')

        if cmds.listRelatives('ddhud_grp'):
            return

        '''
        @读取json文件
        '''
        config_file = ("%shud_config.json" % cmds.internalVar(usd=True))
        if not os.path.exists(config_file):
            config_file = ("%s/scripts/hud_config.json" % ddhud_path)

        data = cls.readJson(config_file)
        print (data)
        '''
        @遍历数据表
        @生成节点
        '''
        for key,value in data.items():
            hud_node = cmds.createNode("DDHUD",n=('%s_hud' % key))
            cmds.rename(cmds.listRelatives(hud_node,ap=True)[0],key)
            cmds.parent(key,'ddhud_grp')
            cmds.setAttr(("%s.border" % hud_node),0)
            cmds.setAttr(("%s.borderWidth" % hud_node),50)
            cmds.setAttr(("%s.fontName" % hud_node),"Times New Roman",type='string')

            for v in value:
                if v[0] == 'text':
                    cmds.setAttr(("%s.%s" % (hud_node,v[0])),v[1],type="string")
                else:
                    cmds.setAttr(("%s.%s" % (hud_node,v[0])),float(v[1]))
        cls.create_exp()

    @classmethod
    def readJson(cls,path=None):
        '''
        @读取json文件
        '''
        if not path:
            return
        with open(path,'r') as f:
            data = json.load(f)
        return data

    @classmethod
    def get_now_time(cls):
        """
        获取当前日期时间
        :return:当前日期时间
        """
        now =  time.localtime()
        # now_time = time.strftime("%Y-%m-%d %H:%M:%S", now)
        now_time = time.strftime("%Y-%m-%d ", now)
        return now_time

    @classmethod
    def getFrameRate(cls):
        '''
        获取文件的帧数率
        '''
        currentUnit = cmds.currentUnit(query=True, time=True)
        if currentUnit == 'film':
            return 24
        if currentUnit == 'show':
            return 48
        if currentUnit == 'pal':
            return 25
        if currentUnit == 'ntsc':
            return 30
        if currentUnit == 'palf':
            return 50
        if currentUnit == 'ntscf':
            return 60
        if 'fps' in currentUnit:
            return currentUnit[:-3]

    @classmethod
    def create_exp(cls):
        # 获取文件名
        if cmds.objExists('file_name_hud'):
            if not cmds.file(q=True,sn=True):
                cmds.confirmDialog( t=u'警告', m=u'未检测到文件名!!\n需要手动输入',icn='warning', b=['Yes'], db='Yes', ds='No' )
                cmds.setAttr('file_name_hud.text',
                            ('%s:untitled' % (cmds.getAttr('file_name_hud.text').split(":")[0])),
                            type='string')
            else:
                filename = os.path.split(os.path.splitext(cmds.file(q=True,sn=True))[0])[1]
                cmds.setAttr('file_name_hud.text',
                            ('%s:%s' % (cmds.getAttr('file_name_hud.text').split(":")[0],filename)),
                            type='string')

        # 获取当前帧数                    
        if cmds.objExists('frame_hud'):
            frame_text = cmds.getAttr('frame_hud.text').split(":")[0]
        
        try:
            frame_exp = ('\"string $num = `currentTime -q`;\n' +
                        'string $pad = `python (\"\'%04d\' % \"+$num)`;\n' +
                        'setAttr -type \"string\" frame_hud.text (\"%s:\" + $pad);\"' % frame_text)

            cmds.expression(o="",n="frame_hud_exp",ae=1,uc=all,s=frame_exp)
        except:
            return 
        
        # 获取帧数范围
        if cmds.objExists('time_range_hud'):
            start_frame = ('%04d' % cmds.playbackOptions(q=True,min=True))
            end_frame = ('%04d' % cmds.playbackOptions(q=True,max=True))
            cmds.setAttr('time_range_hud.text',
                        ('%s:%s-%s'%(cmds.getAttr('time_range_hud.text').split(":")[0],
                        start_frame,end_frame)),
                        type='string')

        # 获取时间
        if cmds.objExists('date_hud'):
            cmds.setAttr('date_hud.text',
                        ('%s:%s' % (cmds.getAttr('date_hud.text').split(":")[0]
                        ,cls.get_now_time())),
                        type='string')

        # 获取计算名
        if cmds.objExists('author_hud'):
            cmds.setAttr('author_hud.text',
            ('%s:%s' % (cmds.getAttr('author_hud.text').split(":")[0]
            ,os.environ.get("username"))),
            type='string')

        # 获取帧数率
        if cmds.objExists('fps'):
            cmds.setAttr('fps_hud.text',
            ('%s%s'% (cmds.getAttr('fps.text').split(":")[0],cls.getFrameRate())),
            type='string')

class Playblast(QObject):

    RESOLUTION_PRESETS = [
        ["Render", ()],
    ]
    FRAME_RANGE_PRESETS = [
        "Animation",
        "Playback",
        "Render",
        "Camera",
    ]

    VIDEO_ENCODER_LOOKUP = {
        "mov": ["h264"],
        "mp4": ["h264"],
        "Image": ["jpg", "png", "tif"],
    }

    H264_QUALITIES = {
        "Very High": 18,
        "High": 20,
        "Medium": 23,
        "Low": 26,
    }

    H264_PRESETS = [
        "veryslow",
        "slow",
        "medium",
        "fast",
        "faster",
        "ultrafast",
    ]

    DEFAULT_CAMERA = None
    DEFAULT_RESOLUTION = "Render"
    DEFAULT_FRAME_RANGE = "Playback"

    DEFAULT_CONTAINER = "mp4"
    DEFAULT_ENCODER = "h264"
    DEFAULT_H264_QUALITY = "Very High"
    DEFAULT_H264_PRESET = "fast"
    DEFAULT_IMAGE_QUALITY = 100

    DEFAULT_VISIBILITY = "Viewport"

    DEFAULT_PADDING = 4

    DEFAULT_MAYA_LOGGING_ENABLED = False

    CAMERA_PLAYBLAST_START_ATTR = "playblastStart"
    CAMERA_PLAYBLAST_END_ATTR = "playblastEnd"

    output_logged = Signal(str)

    def __init__(self):
        super(Playblast, self).__init__()
        self.set_maya_logging_enabled(Playblast.DEFAULT_MAYA_LOGGING_ENABLED)

        self.build_presets()

        self.set_camera(Playblast.DEFAULT_CAMERA)
        self.set_resolution(Playblast.DEFAULT_RESOLUTION)

        self.set_encoding(Playblast.DEFAULT_CONTAINER, Playblast.DEFAULT_ENCODER)
        self.set_h264_settings(Playblast.DEFAULT_H264_QUALITY, Playblast.DEFAULT_H264_PRESET)
        self.set_image_settings(Playblast.DEFAULT_IMAGE_QUALITY)

        self.initialize_ffmpeg_process()
        
    def build_presets(self):
        self.resolution_preset_names = []
        self.resolution_presets = {}

        for preset in Playblast.RESOLUTION_PRESETS:
            self.resolution_preset_names.append(preset[0])
            self.resolution_presets[preset[0]] = preset[1]
    
        try:
            for preset in PlayblastCustomPresets.RESOLUTION_PRESETS:
                self.resolution_preset_names.append(preset[0])
                self.resolution_presets[preset[0]] = preset[1]
        except:
            traceback.print_exc()
            self.log_error("Failed to add custom resolution presets. See script editor for details.")

    #设置与maya反馈窗口关联
    def set_maya_logging_enabled(self, enabled):
        self._log_to_maya = enabled

    def is_maya_logging_enabled(self):
        return self._log_to_maya

    def set_camera(self, camera):
        if camera and camera not in cmds.listCameras():
            self.log_error("Camera does not exist: {0}".format(camera))
            camera = None

        self._camera = camera

    def set_resolution(self, resolution):
        self._resolution_preset = None

        try:
            widthHeight = self.preset_to_resolution(resolution)
            self._resolution_preset = resolution
        except:
            widthHeight = resolution

        valid_resolution = True
        try:
            if not (isinstance(widthHeight[0], int) and isinstance(widthHeight[1], int)):
                valid_resolution = False
        except:
            valid_resolution = False

        if valid_resolution:
            if widthHeight[0] <=0 or widthHeight[1] <= 0:
                self.log_error("Invalid resolution: {0}. Values must be greater than zero.".format(widthHeight))
                return
        else:
            self.log_error("Invalid resoluton: {0}. Expected one of [int, int], {1}".format(widthHeight, ", ".join(self.resolution_preset_names)))
            return

        self._widthHeight = (widthHeight[0], widthHeight[1])

    def get_viewport_panel(self):
        model_panel = cmds.getPanel(withFocus=True)
        try:
            cmds.modelPanel(model_panel, q=True, modelEditor=True)
        except:
            return None

        return model_panel

    def get_resolution_width_height(self):
        if self._resolution_preset:
            return self.preset_to_resolution(self._resolution_preset)

        return self._widthHeight

    def preset_to_resolution(self, resolution_preset_name):
        if resolution_preset_name == "Render":
            width = cmds.getAttr("defaultResolution.width")
            height = cmds.getAttr("defaultResolution.height")
            return (width, height)
        elif resolution_preset_name in self.resolution_preset_names:
            return self.resolution_presets[resolution_preset_name]
        else:
            raise RuntimeError("Invalid resolution preset: {0}".format(resolution_preset_name))

    def set_encoding(self, container_format, encoder):
        if container_format not in Playblast.VIDEO_ENCODER_LOOKUP.keys():
            self.log_error("Invalid container: {0}. Expected one of {1}".format(container_format, Playblast.VIDEO_ENCODER_LOOKUP.keys()))
            return

        if encoder not in Playblast.VIDEO_ENCODER_LOOKUP[container_format]:
            self.log_error("Invalid encoder: {0}. Expected one of {1}".format(encoder, Playblast.VIDEO_ENCODER_LOOKUP[container_format]))
            return

        self._container_format = container_format
        self._encoder = encoder
    
    def set_h264_settings(self, quality, preset):
        if not quality in Playblast.H264_QUALITIES.keys():
            self.log_error("Invalid h264 quality: {0}. Expected one of {1}".format(quality, Playblast.H264_QUALITIES.keys()))
            return

        if not preset in Playblast.H264_PRESETS:
            self.log_error("Invalid h264 preset: {0}. Expected one of {1}".format(preset, Playblast.H264_PRESETS))
            return

        self._h264_quality = quality
        self._h264_preset = preset

    def get_h264_settings(self):
        return {
            "quality": self._h264_quality,
            "preset": self._h264_preset,
        }

    def set_image_settings(self, quality):
        if quality > 0 and quality <= 100:
            self._image_quality = quality
        else:
            self.log_error("Invalid image quality: {0}. Expected value between 1-100")

    def get_image_settings(self):
        return {
            "quality": self._image_quality,
        }

    def execute(self, output_dir, filename, padding=4, camera_override="", enable_camera_frame_range=False):

        ffmpeg_path = PlayblastUtils.get_ffmpeg_path(ddhud_path)

        viewport_model_panel = self.get_viewport_panel()
        if not viewport_model_panel:
            self.log_error("An active viewport is not selected. Select a viewport and retry.")
            return

        if not output_dir:
            self.log_error("Output directory path not set")
            return
        if not filename:
            self.log_error("Output file name not set")
            return

        # Store original camera
        orig_camera = self.get_active_camera()

        if camera_override:
            camera = camera_override
        else:
            camera = self._camera

        if not camera:
            camera = orig_camera

        if not camera in cmds.listCameras():
            self.log_error("Camera does not exist: {0}".format(camera))
            return

        output_dir = self.resolve_output_directory_path(output_dir)
        filename = self.resolve_output_filename(filename, camera)

        if padding <= 0:
            padding = Playblast.DEFAULT_PADDING

        output_path = os.path.normpath(os.path.join(output_dir, "{0}.{1}".format(filename, self._container_format)))

        playblast_output_dir = "{0}/playblast_temp".format(output_dir)
        playblast_output = os.path.normpath(os.path.join(playblast_output_dir, filename))
        force_overwrite = True
        compression = "png"
        image_quality = 100
        index_from_zero = True
        viewer = False

        widthHeight = self.get_resolution_width_height()
        start_frame, end_frame = self.get_start_end_frame()

        if enable_camera_frame_range:
            if cmds.attributeQuery(Playblast.CAMERA_PLAYBLAST_START_ATTR, node=camera, exists=True) and cmds.attributeQuery(Playblast.CAMERA_PLAYBLAST_END_ATTR, node=camera, exists=True):
                try:
                    start_frame = int(cmds.getAttr("{0}.{1}".format(camera, Playblast.CAMERA_PLAYBLAST_START_ATTR)))
                    end_frame = int(cmds.getAttr("{0}.{1}".format(camera, Playblast.CAMERA_PLAYBLAST_END_ATTR)))

                    self.log_output("Camera frame range enabled for '{0}' camera: ({1}, {2})\n".format(camera, start_frame, end_frame))
                except:
                    self.log_warning("Camera frame range disabled. Invalid attribute type(s) on '{0}' camera (expected integer or float). Defaulting to Playback range.\n".format(camera))

            else:
                self.log_warning("Camera frame range disabled. Attributes '{0}' and '{1}' do not exist on '{2}' camera. Defaulting to Playback range.\n".format(Playblast.CAMERA_PLAYBLAST_START_ATTR, Playblast.CAMERA_PLAYBLAST_END_ATTR, camera))

        if start_frame > end_frame:
            self.log_error("Invalid frame range. The start frame ({0}) is greater than the end frame ({1}).".format(start_frame, end_frame))
            return


        options = {
            "filename": playblast_output,
            "widthHeight": widthHeight,
            "percent": 100,
            "startTime": start_frame,
            "endTime": end_frame,
            "clearCache": True,
            "forceOverwrite": force_overwrite,
            "format": "image",
            "compression": compression,
            "quality": image_quality,
            "indexFromZero": index_from_zero,
            "framePadding": padding,
            "viewer": viewer,
        }

        self.log_output("Starting '{0}' playblast...".format(camera))
        self.log_output("Playblast options: {0}\n".format(options))
        QCoreApplication.processEvents()

        self.set_active_camera(camera)

        overscan_attr = "{0}.overscan".format(camera)
        cmds.setAttr(overscan_attr, 1.1)

        playblast_failed = False
        try:
            cmds.playblast(**options)
        except:
            traceback.print_exc()
            self.log_error("Failed to create playblast. See script editor for details.")
            playblast_failed = True
        finally:
            # Restore original viewport settings
            self.set_active_camera(orig_camera)

        if playblast_failed:
            return

        source_path = "{0}/{1}.%0{2}d.png".format(playblast_output_dir, filename, padding)

        if self._encoder == "h264":
            self.encode_h264(ffmpeg_path, source_path, output_path, start_frame)
        else:
            self.log_error("Encoding failed. Unsupported encoder ({0}) for container ({1}).".format(self._encoder, self._container_format))
            self.remove_temp_dir(playblast_output_dir)
            return

        self.remove_temp_dir(playblast_output_dir)

        self.open_in_viewer(output_path)

        if cmds.objExists('ddhud_grp'):
            cmds.delete('ddhud_grp')

        self.log_output("Playblast complete\n")

    def remove_temp_dir(self, temp_dir_path):
        playblast_dir = QDir(temp_dir_path)
        playblast_dir.setNameFilters(["*.png"])
        playblast_dir.setFilter(QDir.Files)
        for f in playblast_dir.entryList():
            playblast_dir.remove(f)

        if not playblast_dir.rmdir(temp_dir_path):
            self.log_warning("Failed to remove temporary directory: {0}".format(temp_dir_path))

    def open_in_viewer(self, path):
        if not os.path.exists(path):
            self.log_error("Failed to open in viewer. File does not exists: {0}".format(path))
            return

        if self._container_format in ("mov", "mp4") and cmds.optionVar(exists="PlayblastCmdQuicktime"):
            executable_path = cmds.optionVar(q="PlayblastCmdQuicktime")
            if executable_path:
                QProcess.startDetached(executable_path, [path])
                return

        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def set_frame_range(self, frame_range):
        resolved_frame_range = self.resolve_frame_range(frame_range)
        if not resolved_frame_range:
            return

        self._frame_range_preset = None
        if frame_range in Playblast.FRAME_RANGE_PRESETS:
            self._frame_range_preset = frame_range

        self._start_frame = resolved_frame_range[0]
        self._end_frame = resolved_frame_range[1]

    def initialize_ffmpeg_process(self):
        self._ffmpeg_process = QProcess()
        self._ffmpeg_process.readyReadStandardError.connect(self.process_ffmpeg_output)

    def execute_ffmpeg_command(self, program, arguments):
        self._ffmpeg_process.start(program, arguments)
        if self._ffmpeg_process.waitForStarted():
            while self._ffmpeg_process.state() != QProcess.NotRunning:
                QCoreApplication.processEvents()
                QThread.usleep(10)

    def process_ffmpeg_output(self):
        byte_array_output = self._ffmpeg_process.readAllStandardError()

        if sys.version_info.major < 3:
            output = str(byte_array_output)
        else:
            output = str(byte_array_output, "utf-8")

        self.log_output(output)

    def encode_h264(self, ffmpeg_path, source_path, output_path, start_frame):
        self.log_output("Starting h264 encoding...")

        framerate = self.get_frame_rate()

        audio_file_path, audio_frame_offset = self.get_audio_attributes()
        if audio_file_path:
            audio_offset = self.get_audio_offset_in_sec(start_frame, audio_frame_offset, framerate)

        crf = Playblast.H264_QUALITIES[self._h264_quality]
        preset = self._h264_preset

        arguments = []
        arguments.append("-y")
        arguments.extend(["-framerate", "{0}".format(framerate), "-i", source_path])

        if audio_file_path:
            arguments.extend(["-ss", "{0}".format(audio_offset), "-i", audio_file_path])

        arguments.extend(["-c:v", "libx264", "-crf:v", "{0}".format(crf), "-preset:v", preset, "-profile:v", "high", "-pix_fmt", "yuv420p"])

        if audio_file_path:
            arguments.extend(["-filter_complex", "[1:0] apad", "-shortest"])

        arguments.append(output_path)

        self.log_output("ffmpeg arguments: {0}\n".format(arguments))

        self.execute_ffmpeg_command(ffmpeg_path, arguments)

    def get_frame_rate(self):
        rate_str = cmds.currentUnit(q=True, time=True)

        if rate_str == "game":
            frame_rate = 15.0
        elif rate_str == "film":
            frame_rate = 24.0
        elif rate_str == "pal":
            frame_rate = 25.0
        elif rate_str == "ntsc":
            frame_rate = 30.0
        elif rate_str == "show":
            frame_rate = 48.0
        elif rate_str == "palf":
            frame_rate = 50.0
        elif rate_str == "ntscf":
            frame_rate = 60.0
        elif rate_str.endswith("fps"):
            frame_rate = float(rate_str[0:-3])
        else:
            raise RuntimeError("Unsupported frame rate: {0}".format(rate_str))

        return frame_rate

    def get_audio_attributes(self):
        sound_node = mel.eval("timeControl -q -sound $gPlayBackSlider;")
        if sound_node:
            file_path = cmds.getAttr("{0}.filename".format(sound_node))
            file_info = QFileInfo(file_path)
            if file_info.exists():
                offset = cmds.getAttr("{0}.offset".format(sound_node))

                return (file_path, offset)

        return (None, None)

    def get_audio_offset_in_sec(self, start_frame, audio_frame_offset, frame_rate):
        return (start_frame - audio_frame_offset) / frame_rate

    def get_start_end_frame(self):
        if self._frame_range_preset:
            return self.preset_to_frame_range(self._frame_range_preset)

        return (self._start_frame, self._end_frame)

    def resolve_frame_range(self, frame_range):
        try:
            if type(frame_range) in [list, tuple]:
                start_frame = frame_range[0]
                end_frame = frame_range[1]
            else:
                start_frame, end_frame = self.preset_to_frame_range(frame_range)

            return (start_frame, end_frame)

        except:
            presets = []
            for preset in Playblast.FRAME_RANGE_PRESETS:
                presets.append("'{0}'".format(preset))
            self.log_error('Invalid frame range. Expected one of (start_frame, end_frame), {0}'.format(", ".join(presets)))

        return None

    def preset_to_frame_range(self, frame_range_preset):
        if frame_range_preset == "Render":
            start_frame = int(cmds.getAttr("defaultRenderGlobals.startFrame"))
            end_frame = int(cmds.getAttr("defaultRenderGlobals.endFrame"))
        elif frame_range_preset == "Playback":
            if mel.eval("timeControl -q -rangeVisible $gPlayBackSlider"):
                start_frame, end_frame = mel.eval("timeControl -q -rangeArray $gPlayBackSlider")
                end_frame = end_frame - 1
            else:
                start_frame = int(cmds.playbackOptions(q=True, minTime=True))
                end_frame = int(cmds.playbackOptions(q=True, maxTime=True))
        elif frame_range_preset == "Animation":
            start_frame = int(cmds.playbackOptions(q=True, animationStartTime=True))
            end_frame = int(cmds.playbackOptions(q=True, animationEndTime=True))
        elif frame_range_preset == "Camera":
            return self.preset_to_frame_range("Playback")
        else:
            raise RuntimeError("Invalid frame range preset: {0}".format(frame_range_preset))

        return (start_frame, end_frame)

    def resolve_output_directory_path(self, dir_path):
        dir_path = PlayblastCustomPresets.parse_playblast_output_dir_path(dir_path)

        if "{project}" in dir_path:
            dir_path = dir_path.replace("{project}", self.get_project_dir_path())

        return dir_path

    def resolve_output_filename(self, filename, camera):
        filename = PlayblastCustomPresets.parse_playblast_output_filename(filename)

        if "{scene}" in filename:
            filename = filename.replace("{scene}", self.get_scene_name())
        if "{timestamp}" in filename:
            filename = filename.replace("{timestamp}", self.get_timestamp())

        if "{camera}" in filename:
            new_camera_name = camera

            new_camera_name = new_camera_name.split(':')[-1]
            new_camera_name = new_camera_name.split('|')[-1]

            filename = filename.replace("{camera}", new_camera_name)

        return filename

    def get_viewport_panel(self):
        model_panel = cmds.getPanel(withFocus=True)
        try:
            cmds.modelPanel(model_panel, q=True, modelEditor=True)
        except:
            return None

        return model_panel

    def get_project_dir_path(self):
        return cmds.workspace(q=True, rootDirectory=True)

    def get_active_camera(self):
        model_panel = self.get_viewport_panel()
        if not model_panel:
            self.log_error("Failed to get active camera. A viewport is not active.")
            return None

        return cmds.modelPanel(model_panel, q=True, camera=True)

    def set_active_camera(self, camera):
        model_panel = self.get_viewport_panel()
        if model_panel:
            mel.eval("lookThroughModelPanel {0} {1}".format(camera, model_panel))
        else:
            self.log_error("Failed to set active camera. A viewport is not active.")

    #日志设置
    def log_error(self, text):
        if self._log_to_maya:
            om.MGlobal.displayError("[Playblast] {0}".format(text))

        self.output_logged.emit("[ERROR] {0}".format(text))  # pylint: disable=E1101

    def log_warning(self, text):
        if self._log_to_maya:
            om.MGlobal.displayWarning("[Playblast] {0}".format(text))

        self.output_logged.emit("[WARNING] {0}".format(text))  # pylint: disable=E1101

    def log_output(self, text):
        if self._log_to_maya:
            om.MGlobal.displayInfo(text)

        self.output_logged.emit(text)  # pylint: disable=E1101

# 主控件 功能
class playblastWidget(QWidget):
    
    HUD_LOCATION_RANGE = [0,200]
    
    collapsed_state_changed = Signal()

    def __init__(self, parent=None):
        super(playblastWidget,self).__init__(parent)

        self._playblast = Playblast()
        self.hud_labels = PlayblastCustomPresets.HUD_MASKS_LABELS


        self.create_widgets()
        self.create_layouts()
        self.create_connections()

    def create_widgets(self):
        button_height = 19
        combo_box_min_width = 100

        self.output_path_label = QLabel(u'输出路径')
        self.output_path_tx = QLineEdit()
        self.filepathbrowse_btn = QPushButton('<<<')
        self.filepathbrowse_btn.setFixedWidth(50)
        self.filepathbrowse_btn.setToolTip(u'选择要保存的路径及文件名')

        self.currentfile_btn = QPushButton('M')
        self.currentfile_btn.setFixedWidth(30)
        self.currentfile_btn.setToolTip(u'按当前文件保存路径保存')

        self.font_size_label = QLabel(u'大小')
        self.font_size_slider = QSlider()
        self.font_size_slider.setRange(1,100)
        self.font_size_slider.setOrientation(Qt.Horizontal)

        self.font_color_label = QLabel(u'颜色')
        self.font_color_btn = playblastColorButton()

        self.resolution_select_cmb = QComboBox()
        self.resolution_select_cmb.setMinimumWidth(combo_box_min_width)
        self.resolution_select_cmb.addItems(self._playblast.resolution_preset_names)
        self.resolution_select_cmb.addItem("Custom")

        self.resolution_width_sb = QSpinBox()
        self.resolution_width_sb.setButtonSymbols(QSpinBox.NoButtons)
        self.resolution_width_sb.setRange(1, 9999)
        self.resolution_width_sb.setMinimumWidth(40)
        self.resolution_width_sb.setAlignment(Qt.AlignRight)
        self.resolution_height_sb = QSpinBox()
        self.resolution_height_sb.setButtonSymbols(QSpinBox.NoButtons)
        self.resolution_height_sb.setRange(1, 9999)
        self.resolution_height_sb.setMinimumWidth(40)
        self.resolution_height_sb.setAlignment(Qt.AlignRight)

        self.camera_select_cmb = QComboBox()
        self.camera_select_cmb.setMinimumWidth(combo_box_min_width)
        self.camera_select_hide_defaults_cb = QCheckBox("Hide defaults")
        self.refresh_cameras()

        self.company_tx = QLineEdit()
        self.company_name_X_slider = QSlider()
        self.company_name_X_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.company_name_X_slider.setOrientation(Qt.Horizontal)
        self.company_name_X_slider.setObjectName("%s_X_slider" % self.hud_labels[6])
        self.company_name_Y_slider = QSlider()
        self.company_name_Y_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.company_name_Y_slider.setOrientation(Qt.Horizontal)
        self.company_name_Y_slider.setObjectName("%s_Y_slider" % self.hud_labels[6])

        self.proj_name_tx = QLineEdit()
        self.proj_name_X_slider = QSlider()
        self.proj_name_X_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.proj_name_X_slider.setOrientation(Qt.Horizontal)
        self.proj_name_X_slider.setObjectName("%s_X_slider" % self.hud_labels[9])
        self.proj_name_Y_slider = QSlider()
        self.proj_name_Y_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.proj_name_Y_slider.setOrientation(Qt.Horizontal)
        self.proj_name_Y_slider.setObjectName("%s_Y_slider" % self.hud_labels[9])

        self.file_name_tx = QLineEdit()
        self.file_name_X_slider = QSlider()
        self.file_name_X_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.file_name_X_slider.setOrientation(Qt.Horizontal)
        self.file_name_X_slider.setObjectName("%s_X_slider" % self.hud_labels[2])
        self.file_name_Y_slider = QSlider()
        self.file_name_Y_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.file_name_Y_slider.setOrientation(Qt.Horizontal)
        self.file_name_Y_slider.setObjectName("%s_Y_slider" % self.hud_labels[2])

        self.author_tx = QLineEdit()
        self.author_X_slider = QSlider()
        self.author_X_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.author_X_slider.setOrientation(Qt.Horizontal)
        self.author_X_slider.setObjectName("%s_X_slider" % self.hud_labels[1])
        self.author_Y_slider = QSlider()
        self.author_Y_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.author_Y_slider.setOrientation(Qt.Horizontal)
        self.author_Y_slider.setObjectName("%s_Y_slider" % self.hud_labels[1])

        self.frame_range_cmb = QComboBox()
        self.frame_range_cmb.setMinimumWidth(combo_box_min_width)
        self.frame_range_cmb.addItems(Playblast.FRAME_RANGE_PRESETS)
        self.frame_range_cmb.addItem("Custom")
        self.frame_range_cmb.setCurrentText(Playblast.DEFAULT_FRAME_RANGE)

        self.frame_range_start_sb = QSpinBox()
        self.frame_range_start_sb.setButtonSymbols(QSpinBox.NoButtons)
        self.frame_range_start_sb.setRange(-9999, 9999)
        self.frame_range_start_sb.setMinimumWidth(40)
        self.frame_range_start_sb.setAlignment(Qt.AlignRight)

        self.frame_range_end_sb = QSpinBox()
        self.frame_range_end_sb.setButtonSymbols(QSpinBox.NoButtons)
        self.frame_range_end_sb.setRange(-9999, 9999)
        self.frame_range_end_sb.setMinimumWidth(40)
        self.frame_range_end_sb.setAlignment(Qt.AlignRight)

        self.time_range_X_slider = QSlider()
        self.time_range_X_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.time_range_X_slider.setOrientation(Qt.Horizontal)
        self.time_range_X_slider.setObjectName("%s_X_slider" % self.hud_labels[4])
        self.time_range_Y_slider = QSlider()
        self.time_range_Y_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.time_range_Y_slider.setOrientation(Qt.Horizontal)
        self.time_range_Y_slider.setObjectName("%s_Y_slider" % self.hud_labels[4])

        self.fps_X_slider = QSlider()
        self.fps_X_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.fps_X_slider.setOrientation(Qt.Horizontal)
        self.fps_X_slider.setObjectName("%s_X_slider" % self.hud_labels[7])
        self.fps_Y_slider = QSlider()
        self.fps_Y_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.fps_Y_slider.setOrientation(Qt.Horizontal)
        self.fps_Y_slider.setObjectName("%s_Y_slider" % self.hud_labels[7])

        self.focal_length_X_slider = QSlider()
        self.focal_length_X_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.focal_length_X_slider.setOrientation(Qt.Horizontal)
        self.focal_length_X_slider.setObjectName("%s_X_slider" % self.hud_labels[0])
        self.focal_length_Y_slider = QSlider()
        self.focal_length_Y_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.focal_length_Y_slider.setOrientation(Qt.Horizontal)
        self.focal_length_Y_slider.setObjectName("%s_Y_slider" % self.hud_labels[0])

        self.frame_X_slider = QSlider()
        self.frame_X_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.frame_X_slider.setOrientation(Qt.Horizontal)
        self.frame_X_slider.setObjectName("%s_X_slider" % self.hud_labels[3])
        self.frame_Y_slider = QSlider()
        self.frame_Y_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.frame_Y_slider.setOrientation(Qt.Horizontal)
        self.frame_Y_slider.setObjectName("%s_Y_slider" % self.hud_labels[3])

        self.date_X_slider = QSlider()
        self.date_X_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.date_X_slider.setOrientation(Qt.Horizontal)
        self.date_X_slider.setObjectName("%s_X_slider" % self.hud_labels[8])
        self.date_Y_slider = QSlider()
        self.date_Y_slider.setRange(playblastWidget.HUD_LOCATION_RANGE[0],playblastWidget.HUD_LOCATION_RANGE[1])
        self.date_Y_slider.setOrientation(Qt.Horizontal)
        self.date_Y_slider.setObjectName("%s_Y_slider" % self.hud_labels[8])

        self.output_edit = QPlainTextEdit()
        self.output_edit.setFocusPolicy(Qt.NoFocus)
        self.output_edit.setReadOnly(True)
        self.output_edit.setWordWrapMode(QTextOption.NoWrap)

        self.log_to_script_editor_cb = QCheckBox("Log to Script Editor")
        self.log_to_script_editor_cb.setChecked(self._playblast.is_maya_logging_enabled())

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setMinimumWidth(70)
        self.clear_btn.setFixedHeight(button_height)

    def create_layouts(self):

        output_path_layout = QHBoxLayout()
        output_path_layout.addWidget(self.output_path_label)
        output_path_layout.addWidget(self.output_path_tx)
        output_path_layout.addWidget(self.filepathbrowse_btn)
        output_path_layout.addWidget(self.currentfile_btn)

        self.output_GB = QGroupBox(u'输出设置')
        self.output_GB.setStyleSheet("QGroupBox{\n"
                                            "font:75 14px Microsoft JhengHei UI;\n"
                                            "}\n"
                                            "")
        self.output_GBLay = QVBoxLayout(self.output_GB)
        self.output_GBLay.addLayout(output_path_layout)

        self.font_size_lay = QHBoxLayout()
        self.font_size_lay.addWidget(self.font_size_label)
        self.font_size_lay.addWidget(self.font_size_slider)

        self.font_color_lay = QHBoxLayout()
        self.font_color_lay.addWidget(self.font_color_label)
        self.font_color_lay.addWidget(self.font_color_btn)

        global_setting_layout = QVBoxLayout()
        global_setting_layout.addLayout(self.font_size_lay)
        global_setting_layout.addLayout(self.font_color_lay)

        resolution_layout = QHBoxLayout()
        resolution_layout.setSpacing(2)
        resolution_layout.addWidget(self.resolution_select_cmb)
        resolution_layout.addSpacing(1)
        resolution_layout.addWidget(self.resolution_width_sb)
        resolution_layout.addWidget(QLabel("x"))
        resolution_layout.addWidget(self.resolution_height_sb)
        resolution_layout.addStretch()

        camera_options_layout = QHBoxLayout()
        camera_options_layout.setSpacing(2)
        camera_options_layout.addWidget(self.camera_select_cmb)
        camera_options_layout.addWidget(self.camera_select_hide_defaults_cb)
        camera_options_layout.addStretch()

        global_layout = playblastFormLayout()
        # options_layout.setVerticalSpacing(5)
        global_layout.addLayoutRow(0, u"输出尺寸:", resolution_layout)
        global_layout.addLayoutRow(1, "Camera:", camera_options_layout)

        self.global_GB = QGroupBox(u'全局设置')
        self.global_GB.setStyleSheet("QGroupBox{\n"
                                            "font:75 14px Microsoft JhengHei UI;\n"
                                            "}\n"
                                            "")
        self.global_GBLay = QVBoxLayout(self.global_GB)
        self.global_GBLay.addLayout(global_setting_layout)  
        self.global_GBLay.addLayout(global_layout)

        company_layout = QHBoxLayout()
        company_layout.setSpacing(2)
        company_layout.addWidget(self.company_tx)
        company_layout.addSpacing(1)
        company_layout.addWidget(QLabel("X"))
        company_layout.addWidget(self.company_name_X_slider)
        company_layout.addWidget(QLabel("Y"))
        company_layout.addWidget(self.company_name_Y_slider)
        company_layout.addStretch()
        
        proj_name_layout = QHBoxLayout()
        proj_name_layout.setSpacing(2)
        proj_name_layout.addWidget(self.proj_name_tx)
        proj_name_layout.addSpacing(1)
        proj_name_layout.addWidget(QLabel("X"))
        proj_name_layout.addWidget(self.proj_name_X_slider)
        proj_name_layout.addWidget(QLabel("Y"))
        proj_name_layout.addWidget(self.proj_name_Y_slider)
        proj_name_layout.addStretch()

        file_name_layout = QHBoxLayout()
        file_name_layout.setSpacing(2)
        file_name_layout.addWidget(self.file_name_tx)
        file_name_layout.addSpacing(1)
        file_name_layout.addWidget(QLabel("X"))
        file_name_layout.addWidget(self.file_name_X_slider)
        file_name_layout.addWidget(QLabel("Y"))
        file_name_layout.addWidget(self.file_name_Y_slider)
        file_name_layout.addStretch()

        author_layout = QHBoxLayout()
        author_layout.setSpacing(2)
        author_layout.addWidget(self.author_tx)
        author_layout.addSpacing(1)
        author_layout.addWidget(QLabel("X"))
        author_layout.addWidget(self.author_X_slider)
        author_layout.addWidget(QLabel("Y"))
        author_layout.addWidget(self.author_Y_slider)
        author_layout.addStretch()

        time_range_layout = QHBoxLayout()
        time_range_layout.addWidget(self.frame_range_cmb)
        time_range_layout.setSpacing(2)
        time_range_layout.addWidget(self.frame_range_start_sb)
        time_range_layout.addWidget(self.frame_range_end_sb)
        time_range_layout.addSpacing(1)
        time_range_layout.addWidget(QLabel("X"))
        time_range_layout.addWidget(self.time_range_X_slider)
        time_range_layout.addWidget(QLabel("Y"))
        time_range_layout.addWidget(self.time_range_Y_slider)
        time_range_layout.addStretch()

        fps_layout = QHBoxLayout()
        fps_layout.addSpacing(2)
        fps_layout.addWidget(QLabel("X"))
        fps_layout.addWidget(self.fps_X_slider)
        fps_layout.addWidget(QLabel("Y"))
        fps_layout.addWidget(self.fps_Y_slider)
        fps_layout.addStretch()

        focal_length_layout = QHBoxLayout()
        focal_length_layout.addSpacing(2)
        focal_length_layout.addWidget(QLabel("X"))
        focal_length_layout.addWidget(self.focal_length_X_slider)
        focal_length_layout.addWidget(QLabel("Y"))
        focal_length_layout.addWidget(self.focal_length_Y_slider)
        focal_length_layout.addStretch()

        frame_layout = QHBoxLayout()
        frame_layout.addSpacing(2)
        frame_layout.addWidget(QLabel("X"))
        frame_layout.addWidget(self.frame_X_slider)
        frame_layout.addWidget(QLabel("Y"))
        frame_layout.addWidget(self.frame_Y_slider)
        frame_layout.addStretch()

        date_layout = QHBoxLayout()
        date_layout.addSpacing(2)
        date_layout.addWidget(QLabel("X"))
        date_layout.addWidget(self.date_X_slider)
        date_layout.addWidget(QLabel("Y"))
        date_layout.addWidget(self.date_Y_slider)
        date_layout.addStretch()


        part_layout = playblastFormLayout()
        part_layout.addLayoutRow(0, u"公司名:", company_layout)
        part_layout.addLayoutRow(1, u"项目名:", proj_name_layout)
        part_layout.addLayoutRow(2, u"文件名:", file_name_layout)
        part_layout.addLayoutRow(3, u"制作者:", author_layout)
        part_layout.addLayoutRow(4, u"帧范围:", time_range_layout)
        part_layout.addLayoutRow(5, u"帧速率:", fps_layout)
        part_layout.addLayoutRow(6, u"焦  距:", focal_length_layout)
        part_layout.addLayoutRow(7, u"当前帧:", frame_layout)
        part_layout.addLayoutRow(8, u"日  期:", date_layout)

        self.part_GB = QGroupBox(u'局部设置')
        self.part_GB.setStyleSheet("QGroupBox{\n"
                                            "font:75 14px Microsoft JhengHei UI;\n"
                                            "}\n"
                                            "")
        self.part_GBLay = QVBoxLayout(self.part_GB)
        self.part_GBLay.addLayout(part_layout)

        logging_button_layout = QHBoxLayout()
        logging_button_layout.setContentsMargins(4, 0, 4, 10)
        logging_button_layout.addWidget(self.log_to_script_editor_cb)
        logging_button_layout.addStretch()
        logging_button_layout.addWidget(self.clear_btn)

        self.logging_GB = QGroupBox(u'输出日志')
        self.logging_GB.setStyleSheet("QGroupBox{\n"
                                            "font:75 14px Microsoft JhengHei UI;\n"
                                            "}\n"
                                            "")
        self.logging_GBLay = QVBoxLayout(self.logging_GB)
        self.logging_GBLay.addWidget(self.output_edit)
        self.logging_GBLay.addLayout(logging_button_layout)


        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)
        main_layout.addWidget(self.output_GB)
        main_layout.addWidget(self.global_GB)
        main_layout.addWidget(self.part_GB)
        main_layout.addWidget(self.logging_GB)

    def create_connections(self):
        self.filepathbrowse_btn.clicked.connect(self.select_output_directory)
        self.currentfile_btn.clicked.connect(self.select_current_output_directory)
        
        self.camera_select_cmb.currentTextChanged.connect(self.on_camera_changed)
        self.camera_select_hide_defaults_cb.toggled.connect(self.refresh_cameras)

        self.resolution_select_cmb.currentTextChanged.connect(self.refresh_resolution)
        self.resolution_width_sb.editingFinished.connect(self.on_resolution_changed)
        self.resolution_height_sb.editingFinished.connect(self.on_resolution_changed)

        self.frame_range_cmb.currentTextChanged.connect(self.refresh_frame_range)
        self.frame_range_start_sb.editingFinished.connect(self.on_frame_range_changed)
        self.frame_range_end_sb.editingFinished.connect(self.on_frame_range_changed)

        self.font_size_slider.valueChanged.connect(self.update_mask_size)
        self.font_color_btn.color_changed.connect(self.update_mask_color)

        self.company_name_X_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[6],"x"))
        self.company_name_Y_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[6],"y"))

        self.proj_name_X_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[9],"x"))
        self.proj_name_Y_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[9],"y"))

        self.file_name_X_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[2],"x"))
        self.file_name_Y_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[2],"y"))

        self.author_X_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[1],"x"))
        self.author_Y_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[1],"y"))

        self.time_range_X_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[4],"x"))
        self.time_range_Y_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[4],"y"))
        
        self.fps_X_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[7],"x"))
        self.fps_Y_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[7],"y"))

        self.focal_length_X_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[0],"x"))
        self.focal_length_Y_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[0],"y"))

        self.frame_X_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[3],"x"))
        self.frame_Y_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[3],"y"))

        self.date_X_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[8],"x"))
        self.date_Y_slider.valueChanged.connect(partial(self.update_mask_loaction,self.hud_labels[8],"y"))

        self.company_tx.textChanged.connect(partial(self.update_info_le,self.hud_labels[6]))
        self.proj_name_tx.textChanged.connect(partial(self.update_info_le,self.hud_labels[9]))
        self.file_name_tx.textChanged.connect(partial(self.update_info_le,self.hud_labels[2]))
        self.author_tx.textChanged.connect(partial(self.update_info_le,self.hud_labels[1]))
  
        self._playblast.output_logged.connect(self.append_output)  # pylint: disable=E1101

        self.log_to_script_editor_cb.toggled.connect(self.on_log_to_script_editor_changed)
        self.clear_btn.clicked.connect(self.output_edit.clear)

    def do_playblast(self):
        if not cmds.objExists('ddhud_grp'):
            return
        all_file_path = self.output_path_tx.text()
        if not all_file_path:
            return
        output_dir_path,filename = os.path.split(all_file_path)
        filename = os.path.splitext(filename)[0]

        padding = Playblast.DEFAULT_PADDING

        use_camera_frame_range = self.frame_range_cmb.currentText() == "Camera"

        cmds.evalDeferred(partial(self._playblast.execute, output_dir_path, filename, padding, "", use_camera_frame_range))

    def select_output_directory(self):
        current_dir_path = self.output_path_tx.text()
        if not current_dir_path:
            current_dir_path = self.output_path_tx.placeholderText()

        current_dir_path = self._playblast.resolve_output_directory_path(current_dir_path)

        file_info = QFileInfo(current_dir_path)
        if not file_info.exists():
            current_dir_path = self._playblast.get_project_dir_path()

        new_dir_path = QFileDialog.getExistingDirectory(self, "Select Directory", current_dir_path)
        if new_dir_path:
            if cmds.file(q=True,sn=True,shn=True):
                self.output_path_tx.setText("%s/%s.mp4" % (new_dir_path, 
                                                        (os.path.splitext(
                                                            os.path.basename(cmds.file(q=True,sn=True))))[0]))
            else:
                cmds.confirmDialog( t=u'警告', m=u'请先保存文件!!',icn='warning', b=['Yes'], db='Yes', ds='No' )

    def select_current_output_directory(self):
        current_dir_path = self.output_path_tx.text()
        if not current_dir_path:
            current_dir_path = self.output_path_tx.placeholderText()

        new_dir_path = "%s.mp4"% os.path.splitext(cmds.file(q=True,sn=True))[0]
        if cmds.file(q=True,sn=True,shn=True):
            self.output_path_tx.setText(new_dir_path)
        else:
            cmds.confirmDialog( t=u'警告', m=u'请先保存文件!!',icn='warning', b=['Yes'], db='Yes', ds='No' )

    def refresh_all(self):
        self.refresh_cameras()
        self.refresh_resolution()
        self.refresh_frame_range()

    def refresh_cameras(self):
        current_camera = self.camera_select_cmb.currentText()
        self.camera_select_cmb.clear()

        self.camera_select_cmb.addItem("<Active>")
        self.camera_select_cmb.addItems(PlayblastUtils.cameras_in_scene(self.camera_select_hide_defaults_cb.isChecked(), True))

        self.camera_select_cmb.setCurrentText(current_camera)

    def on_camera_changed(self):
        camera = self.camera_select_cmb.currentText()

        if camera == "<Active>":
            camera = None
        
        if cmds.objExists('camera_hud'):
            if camera:
                cmds.setAttr('camera_hud.text',camera,type='string')
            else:
                cmds.setAttr('camera_hud.text','',type='string')

        self._playblast.set_camera(camera)
        self.update_cam_fl(camera)

    def refresh_resolution(self):
        resolution_preset = self.resolution_select_cmb.currentText()
        if resolution_preset != "Custom":
            self._playblast.set_resolution(resolution_preset)

            resolution = self._playblast.get_resolution_width_height()
            self.resolution_width_sb.setValue(resolution[0])
            self.resolution_height_sb.setValue(resolution[1])

    def on_resolution_changed(self):
        resolution = (self.resolution_width_sb.value(), self.resolution_height_sb.value())

        for key in self._playblast.resolution_presets.keys():
            if self._playblast.resolution_presets[key] == resolution:
                self.resolution_select_cmb.setCurrentText(key)
                return

        self.resolution_select_cmb.setCurrentText("Custom")

        self._playblast.set_resolution(resolution)

    def refresh_frame_range(self):
        frame_range_preset = self.frame_range_cmb.currentText()
        if frame_range_preset != "Custom":
            frame_range = self._playblast.preset_to_frame_range(frame_range_preset)

            self.frame_range_start_sb.setValue(frame_range[0])
            self.frame_range_end_sb.setValue(frame_range[1])

            self._playblast.set_frame_range(frame_range_preset)

        enable_frame_range_spinboxes = frame_range_preset != "Camera"
        self.frame_range_start_sb.setEnabled(enable_frame_range_spinboxes)
        self.frame_range_end_sb.setEnabled(enable_frame_range_spinboxes)
        if cmds.objExists("time_range_hud.text"):
            cmds.setAttr("time_range_hud.text",
                        (u"帧范围:%04d-%04d" % (
                            frame_range[0],
                            frame_range[1]
                        )),
                        typ='string')

    def on_frame_range_changed(self):
        self.frame_range_cmb.setCurrentText("Custom")

        frame_range = (self.frame_range_start_sb.value(), self.frame_range_end_sb.value())
        if cmds.objExists("time_range_hud.text"):
            cmds.setAttr("time_range_hud.text",
                        (u"帧范围:%04d-%04d" % (
                            self.frame_range_start_sb.value(),
                            self.frame_range_end_sb.value()
                        )),
                        typ='string')

        self._playblast.set_frame_range(frame_range)

    def on_log_to_script_editor_changed(self):
        self._playblast.set_maya_logging_enabled(self.log_to_script_editor_cb.isChecked())

    def update_cam_fl(self,camera):
        if not camera:
            return
        cam_shape = cmds.ls(camera,dag=True,s=True)[0]
        fl_pre_text = u"焦距"
        if cmds.objExists("focal_length_hud_exp"):
            cmds.delete("focal_length_hud_exp")
        else:
            fl_exp = (('\"string $fl_v = `getAttr \"%s.focalLength\"`;\n' % cam_shape)+
                    'string $fl_p = `python(\"\'%.2f\' % \"+$fl_v)`;\n' +
                    ('setAttr -type \"string\" \"focal_length_hud.text\" (\"%s:\" + $fl_p);\"' % fl_pre_text))
            
            cmds.expression(o="",n="focal_length_hud_exp",ae=1,uc=all,s=fl_exp)

    def update_mask_loaction(self,hud_name,axial,slider_value):
        if not cmds.objExists('ddhud_grp'):
            return
        if cmds.objExists(hud_name):
            cmds.setAttr(("%s_hud.%s" % (hud_name,axial.upper())),(slider_value*0.01))

    def update_mask_size(self):
        if not cmds.objExists('ddhud_grp'):
            return
        print (self.font_size_slider.value())
        for hud_masks in PlayblastCustomPresets.HUD_MASKS_LABELS:
            cmds.setAttr(("%s_hud.fontScale" % hud_masks), (self.font_size_slider.value()*0.01))

    def update_mask_color(self):
        if not cmds.objExists('ddhud_grp'):
            return
        label_color = self.font_color_btn.get_color()
        for hud_masks in PlayblastCustomPresets.HUD_MASKS_LABELS:
            print (("%s_hud.fontColor %s" % (hud_masks,label_color)))
            cmds.setAttr(("%s_hud.fontColor" % hud_masks),label_color[0], label_color[1], label_color[2],type="double3")

    def update_info_le(self,hud_text,hud_le):
        if not cmds.objExists(hud_text):
            return
        get_text_le = cmds.getAttr("%s_hud.text" % hud_text)
        pre_text = get_text_le.split(":")[0]
        cmds.setAttr(("%s_hud.text" % hud_text),
                    ("%s:%s" % (pre_text,hud_le)),
                    type='string')

    def writeJson(self,path=None,data={}):
        '''
        @给json文件写入数据
        '''
        if not path:
            return
        with open(path,'w') as f:
            json.dump(data,f,indent=4,ensure_ascii=False,sort_keys=True)

    def export_hud_json(self):
        hud_data = []
        if cmds.objExists('ddhud_grp'):
            for hud in PlayblastCustomPresets.HUD_MASKS_LABELS:
                tx_le = ["text",cmds.getAttr(("%s_hud.text" % hud)).encode("utf-8")]
                x_le = ["x","%.2f"%cmds.getAttr(("%s_hud.x" % hud))]
                y_le = ["y","%.2f"%cmds.getAttr(("%s_hud.y" % hud))]
                fontScale_le = ["fontScale","%.2f"%cmds.getAttr(("%s_hud.fontScale" % hud))]
                hud_data.append([hud,[tx_le,x_le,y_le,fontScale_le]])

        dict_ddhud = dict(hud_data)
        
        self.writeJson(("%shud_config.json" % cmds.internalVar(usd=True)),dict_ddhud)  
        cmds.confirmDialog( t=u'信息', m=u'导出hud 配置完成',icn='information', b=['Yes'], db='Yes', ds='No' )      

    def append_output(self, text):
        self.output_edit.appendPlainText(text)

        cursor = self.output_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_edit.setTextCursor(cursor)

    def log_warning(self, msg):
        self._playblast.log_warning(msg)

    def showEvent(self, e):
        self.refresh_all()

#程序主要布局
class PlayblastUI(QWidget):

    WINDOW_TITLE = "PlayBlast Tools"
    UI_NAME = "PlayBlastTools"

    OPT_VAR_GROUP_STATE = "playblastGroupState"

    ui_instance = None

    @classmethod
    def display(cls):
        if cls.ui_instance:
            cls.ui_instance.show_workspace_control()
        else:
            if PlayblastUtils.load_plugin():
                cls.ui_instance = PlayblastUI()

    @classmethod
    def get_workspace_control_name(cls):
        return "{0}WorkspaceControl".format(cls.UI_NAME)

    def __init__(self):
        super(PlayblastUI, self).__init__()        

        # self.setWindowTitle("PlayBlast Tools")
        self.setObjectName(PlayblastUI.UI_NAME)
        self.setMinimumSize(372,760)

        self.create_widget()
        self.create_layouts()
        self.create_workspace_control()

        self.create_connections()
        
        # 关闭maya默认hud
        huds = cmds.headsUpDisplay(lh=True)
        for hud in huds:
            if cmds.headsUpDisplay(hud,q=True,vis=True):
                cmds.headsUpDisplay(hud,e=True,vis=False)

        # self.setWindowFlags(self.windowFlags() ^ Qt.WindowContextHelpButtonHint)#隐藏界面问号按钮

    def create_widget(self):
        button_width = 120
        button_height = 40
        
        self._warning_label = QLabel(u'温馨提示，拍屏前请先保存文件！！')
        self._warning_label.setMaximumHeight(20)
        self._warning_label.setAlignment(Qt.AlignCenter)
        self._warning_label.setStyleSheet("QLabel{\n"
                                            "color:black;\n"
                                            "background:rgb(0, 255, 0);\n"
                                            "border-radius:5px;\n"
                                            "font:75 20px Microsoft JhengHei UI;\n"
                                            "radius:2px;\n"
                                            "}\n"
                                            "")


        self.playblast_wdg = playblastWidget()
        self.playblast_wdg.setAutoFillBackground(True)

        self.export_mask_btn = QPushButton(u"导出配置")
        self.export_mask_btn.setFixedSize(button_width, button_height)

        self.playblast_btn = QPushButton("Playblast")
        self.playblast_btn.setMinimumSize(button_width, button_height)

        self.refresh_mask_btn = QPushButton(u"HUD")
        self.refresh_mask_btn.setFixedSize(40, button_height)

        font = self.export_mask_btn.font()
        font.setPointSize(10)
        font.setBold(True)
        self.export_mask_btn.setFont(font)
        self.playblast_btn.setFont(font)
        self.refresh_mask_btn.setFont(font)

        pal = self.export_mask_btn.palette()
        pal.setColor(QPalette.Button, QColor(Qt.darkCyan).darker())
        self.export_mask_btn.setPalette(pal)
        self.refresh_mask_btn.setPalette(pal)

    def create_layouts(self):
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addWidget(self.export_mask_btn)
        button_layout.addWidget(self.playblast_btn)
        button_layout.addWidget(self.refresh_mask_btn)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 0)
        main_layout.setSpacing(2)
        main_layout.addWidget(self._warning_label)
        main_layout.addWidget(self.playblast_wdg)
        main_layout.addLayout(button_layout)

    def create_connections(self):
        self.export_mask_btn.clicked.connect(self.playblast_wdg.export_hud_json)

        self.playblast_btn.clicked.connect(self.playblast_wdg.do_playblast)

        self.refresh_mask_btn.clicked.connect(partial(ShotMask.createHUD,ddhud_path))

    def create_workspace_control(self):
        self.workspace_control_instance = playblastWorkspaceControl(self.get_workspace_control_name())
        if self.workspace_control_instance.exists():
            self.workspace_control_instance.restore(self)
        else:
            self.workspace_control_instance.create(self.WINDOW_TITLE, self, ui_script="from playblast_ui import PlayblastUI\nPlayblastUI.display()")

    def on_collapsed_state_changed(self):
        cmds.optionVar(iv=[PlayblastUI.OPT_VAR_GROUP_STATE, self.playblast_wdg.get_collapsed_states()])

    def get_collapsed_states(self):
        collapsed = 0
        
        return collapsed

    def show_workspace_control(self):
        self.workspace_control_instance.set_visible(True)

    def keyPressEvent(self, e):
        pass

    # 点击时间，点击刷新设置
    def event(self, e):
        if e.type() == QEvent.WindowActivate:
            if self.playblast_wdg.isVisible():
                self.playblast_wdg.refresh_all()

        # elif e.type() == QEvent.WindowDeactivate:
        #     if self.playblast_wdg.isVisible():
        #         self.playblast_wdg.save_settings()

        return super(PlayblastUI, self).event(e)

if __name__ == "__main__":
    workspace_control_name = PlayblastUI.get_workspace_control_name()
    if cmds.window(workspace_control_name,ex=True):
        cmds.deleteUI(workspace_control_name)
    
    zap_test_ui = PlayblastUI()

