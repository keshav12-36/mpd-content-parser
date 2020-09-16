'''
作者: weimo
创建日期: 2020-09-14 13:13:18
上次编辑时间: 2020-09-16 15:11:49
一个人的命运啊,当然要靠自我奋斗,但是...
'''

import re
from typing import Dict
from pathlib import Path
from argparse import ArgumentParser
from xml.parsers.expat import ParserCreate

# aria2c下载生成的txt命令示例 以及使用代理的示例
# aria2c -i urls.txt -d DownloadPath --https-proxy="http://127.0.0.1:1080" --http-proxy="http://127.0.0.1:1080"

AudioMap = {
    "1":"PCM",
    "mp3":"MP3",
    "mp4a.66":"MPEG2_AAC",
    "mp4a.67":"MPEG2_AAC",
    "mp4a.68":"MPEG2_AAC",
    "mp4a.69":"MP3",
    "mp4a.6B":"MP3",
    "mp4a.40.2":"MPEG4_AAC",
    "mp4a.40.02":"MPEG4_AAC",
    "mp4a.40.5":"MPEG4_AAC",
    "mp4a.40.05":"MPEG4_AAC",
    "mp4a.40.29":"MPEG4_AAC",
    "mp4a.40.42":"MPEG4_XHE_AAC",
    "ac-3":"AC3",
    "mp4a.a5":"AC3",
    "mp4a.A5":"AC3",
    "ec-3":"EAC3",
    "mp4a.a6":"EAC3",
    "mp4a.A6":"EAC3",
    "vorbis":"VORBIS",
    "opus":"OPUS",
    "flac":"FLAC",
    "vp8":"VP8",
    "vp8.0":"VP8",
    "theora":"THEORA",
}

class Links(object):

    def __init__(self, *args):
        basename, duration, content_type, track_key, bandwidth, codecs = args
        self.basename: str = basename
        self.duration: float = duration
        self.content_type: str = content_type
        self.track_key: str = track_key
        self.bandwidth: float = float(bandwidth)
        self.codecs: str = self.get_codecs(codecs)
        self.suffix: str = ".unkonwn" # aria2c下载的文件名后缀
        self.lang: str = ""
        self.resolution: str = ""
        self.urls: list = []

    def get_codecs(self, codecs: str):
        # https://chromium.googlesource.com/chromium/src/media/+/master/base/mime_util_internal.cc
        if re.match("avc(1|3)*", codecs):
            return "H264"
        if re.match("(hev|hvc)1*", codecs):
            return "H265"
        if re.match("vp(09|9)*", codecs):
            return "VP9"
        if codecs in ["wvtt"]:
            return codecs.upper()
        if AudioMap.get(codecs) is None:
            codecs = ""
        else:
            codecs = "AAC" if "AAC" in AudioMap[codecs] else AudioMap[codecs]
        return codecs

    def update(self, duration: float, bandwidth: str):
        _bandwidth = float(bandwidth)
        self.bandwidth = (duration * _bandwidth + self.duration * self.bandwidth) / (self.duration + duration)
        self.duration += duration

    def get_path(self) -> Path:
        filename = f"{self.basename}.{self.track_key}.{self.content_type.title()}.{self.codecs}.{self.bandwidth/1000:.3f}kbps"
        if self.lang != "":
            filename += f".{self.lang}"
        if self.resolution != "":
            filename += f".{self.resolution}"
        print(filename)
        return Path(filename+".txt").resolve()

    def dump_urls(self):
        filepath = self.get_path()
        filepath.write_text("\n".join(self.urls), encoding="utf-8")

class MPDItem(object):
    def __init__(self, name: str = "MPDItem"):
        self.name = name
        self.childs = list()

    def addattr(self, name: str, value):
        self.__setattr__(name, value)

    def addattrs(self, attrs: dict):
        for attr_name, attr_value in attrs.items():
            attr_name: str
            attr_name = attr_name.replace(":", "_")
            self.addattr(attr_name, attr_value)

class MPD(MPDItem):
    def __init__(self, name: str):
        super(MPD, self).__init__(name)

class Period(MPDItem):
    def __init__(self, name: str):
        super(Period, self).__init__(name)
        self.id = None
        self.duration = 0.0

class AdaptationSet(MPDItem):
    def __init__(self, name: str):
        super(AdaptationSet, self).__init__(name)
        self.id = None
        self.contentType = None
        self.lang = None
        self.segmentAlignment = None
        self.maxWidth = None
        self.maxHeight = None
        self.frameRate = None
        self.par = None
        self.width = None
        self.height = None

class Role(MPDItem):
    def __init__(self, name: str):
        super(Role, self).__init__(name)

class Representation(MPDItem):
    def __init__(self, name: str):
        super(Representation, self).__init__(name)
        self.id = None
        self.bandwidth = None
        self.codecs = None
        self.mimeType = None
        self.sar = None
        self.width = None
        self.height = None
        self.audioSamplingRate = None

class SegmentTemplate(MPDItem):
    def __init__(self, name: str):
        super(SegmentTemplate, self).__init__(name)
        self.timescale = None
        self.presentationTimeOffset = None
        self.initialization = None
        self.media = None
        self.startNumber = None

class SegmentTimeline(MPDItem):
    def __init__(self, name: str):
        super(SegmentTimeline, self).__init__(name)

class S(MPDItem):
    def __init__(self, name: str):
        super(S, self).__init__(name)
        self.t = None
        self.d = None
        self.r = None

class ContentProtection(MPDItem):
    def __init__(self, name: str):
        super(ContentProtection, self).__init__(name)
        self.value = None
        self.schemeIdUri = None
        self.cenc_default_KID = None

class cenc_pssh(MPDItem):
    def __init__(self, name: str):
        super(cenc_pssh, self).__init__(name)

class MPDPaser(object):
    def __init__(self, basename: str, xmlraw: str, mode: str):
        self.step = 0
        self.basename = basename
        self.xmlraw = xmlraw
        self.mode = mode
        self.obj = None
        self.parser = None
        self.stack = list()
        self.ar_idid = {} # Dict[str, Links]
        self.objs = {
            "MPD": MPD,
            "Period": Period,
            "AdaptationSet": AdaptationSet,
            "Representation": Representation,
            "SegmentTemplate": SegmentTemplate,
            "SegmentTimeline": SegmentTimeline,
            "S": S,
            "ContentProtection": ContentProtection,
            "cenc:pssh": cenc_pssh,
        }

    def work(self):
        self.parser = ParserCreate()
        self.parser.StartElementHandler = self.handle_start_element
        self.parser.EndElementHandler = self.handle_end_element
        self.parser.CharacterDataHandler = self.handle_character_data
        self.parser.Parse(self.xmlraw)

    def handle_start_element(self, tag, attrs):
        if self.obj is None:
            if tag != "MPD":
                raise Exception("the first tag is not MPD!")
            self.obj: MPD = MPD(tag)
            self.obj.addattrs(attrs)
            self.stack.append(self.obj)
        else:
            if self.objs.get(tag) is None:
                return
            child = self.objs[tag](tag)
            child.addattrs(attrs)
            self.obj.childs.append(child)
            self.obj = child
            self.stack.append(child)

    def handle_end_element(self, tag):
        if self.objs.get(tag) is None:
            return
        if len(self.stack) > 1:
            _ = self.stack.pop(-1)
            self.obj = self.stack[-1]

    def handle_character_data(self, texts):
        pass

    @staticmethod
    def find_child(name: str, parent):
        return [child for child in parent.childs if child.name == name]

    def tree(self, obj):
        print(f"{self.step * '--'}>{obj.name}")
        self.step += 1
        for child in obj.childs:
            self.tree(child)
        self.step -= 1
        print(f"{self.step * '--'}>{obj.name}")

    def generate(self):
        Periods = self.find_child("Period", self.obj)
        for _Period in Periods:
            _Period: Period
            if isinstance(_Period.duration, str):
                duration = re.match("PT(\d+)(\.?\d+)S", _Period.duration)
                duration = float(duration.group(1)) if duration else 0.0
            AdaptationSets = self.find_child("AdaptationSet", _Period)
            for _AdaptationSet in AdaptationSets:
                _AdaptationSet: AdaptationSet
                Representations = self.find_child("Representation", _AdaptationSet)
                for _Representation in Representations:
                    _Representation: Representation
                    self.generate_Segments(duration, _AdaptationSet, _Representation)
        for track_key, links in self.ar_idid.items():
            links: Links
            links.dump_urls()

    def generate_Segments(self, duration: float, _AdaptationSet: AdaptationSet, _Representation: Representation):

        track_key = f"{_AdaptationSet.id}-{_Representation.id}"
        links = Links(
            self.basename, duration, _AdaptationSet.contentType, track_key, 
            _Representation.bandwidth, _Representation.codecs
        )
        if _AdaptationSet.lang is not None:
            links.lang = _AdaptationSet.lang
        links.suffix = "." + _Representation.mimeType.split("/")[0].split("-")[-1]
        if _Representation.mimeType == "video/mp4":
            if _Representation.width is not None:
                links.resolution = f"{_Representation.width}x{_Representation.height}p"
        SegmentTemplates = MPDPaser.find_child("SegmentTemplate", _Representation)
        for _SegmentTemplate in SegmentTemplates:
            _SegmentTemplate: SegmentTemplate
            start_number: int = int(_SegmentTemplate.startNumber)
            if self.ar_idid.get(links.track_key) is None:
                links.urls.append(_SegmentTemplate.initialization)
                self.ar_idid[links.track_key] = links
            else:
                if self.mode == "split":
                    self.ar_idid[links.track_key] = links
                else:
                    self.ar_idid[links.track_key].update(duration, _Representation.bandwidth)
            SegmentTimelines = MPDPaser.find_child("SegmentTimeline", _SegmentTemplate)
            urls = []
            for _SegmentTimeline in SegmentTimelines:
                _SegmentTimeline: SegmentTimeline
                repeat = 0
                SS = MPDPaser.find_child("S", _SegmentTimeline)
                for _S in SS:
                    _S: S
                    repeat += 1 if _S.r is None else int(_S.r)
                for offset in range(repeat):
                    urls.append(_SegmentTemplate.media.replace("$Number$", str(start_number)))
                    start_number += 1
            self.ar_idid[links.track_key].urls.extend(urls)
            if self.mode == "split":
                self.ar_idid[links.track_key].dump_urls()

    @staticmethod
    def show_AdaptationSet(obj: AdaptationSet):
        attrs = []
        for attr_name, attr_value in obj.__dict__.items():
            if attr_name == "childs":
                continue
            if attr_value is None:
                continue
            attrs += [f"{attr_value}"]
        # print(" ".join(attrs))

def main():
    command = ArgumentParser(
        prog="mpd content parser v1.0@xhlove",
        description=(
            "Mpd Content Parser, "
            "extract pssh and generate all tracks download links easily. "
            "Report bug to vvtoolbox.dev@gmail.com"
        )
    )
    command.add_argument("-p", "--path", help="mpd file path.")
    command.add_argument("-m", "--mode", choices=["once", "split"], default="once", help="generate links once time or split to write. Default is once")
    args = command.parse_args()
    if args.path is None:
        args.path = input("paste mpd file path plz:\n")
    xmlpath = Path(args.path).resolve()
    if xmlpath.exists():
        xmlraw = xmlpath.read_text(encoding="utf-8")
        parser = MPDPaser(xmlpath.stem, xmlraw, args.mode)
        parser.work()
        # parser.tree(parser.obj)
        parser.generate()
    else:
        print(f"{str(xmlpath)} is not exists!")


if __name__ == "__main__":
    main()