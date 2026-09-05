const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType,
        ShadingType, PageBreak, Header, Footer, PageNumber, ImageRun } = require("docx");

const F = { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" };
const SHOTS = "D:\\WEB\\zicaiduck\\geo-convert\\tools\\manual\\shots\\";
const border = { style: BorderStyle.SINGLE, size: 1, color: "B8C4D0" };
const borders = { top: border, bottom: border, left: border, right: border };

function pngSize(buf){
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}
function img(file, caption, width){
  width = width || 620;
  const data = fs.readFileSync(SHOTS + file);
  const s = pngSize(data);
  const height = Math.round(width * s.h / s.w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80, after: 40 },
      children: [new ImageRun({ type: "png", data, transformation: { width, height },
        altText: { title: caption, description: caption, name: file } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
      children: [new TextRun({ text: caption, size: 18, color: "5D6D7E", italics: true })] }),
  ];
}

function h1(t){ return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] }); }
function h2(t){ return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] }); }
function p(t, opts){ opts = opts || {}; return new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: t, bold: !!opts.bold, color: opts.color })] }); }
function bullet(t){ return new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60 }, children: [new TextRun(t)] }); }
function bulletB(b, t){ return new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: b, bold: true }), new TextRun(t)] }); }
function step(ref, t){ return new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 80 }, children: [new TextRun(t)] }); }
function code(t){ return new Paragraph({ spacing: { after: 100 }, shading: { fill: "F0F4F8", type: ShadingType.CLEAR }, children: [new TextRun({ text: t, font: { ascii: "Consolas", hAnsi: "Consolas", eastAsia: "Microsoft YaHei" }, size: 20 })] }); }

function cell(t, w, opts){
  opts = opts || {};
  return new TableCell({
    borders, width: { size: w, type: WidthType.DXA },
    shading: opts.head ? { fill: "1B4F72", type: ShadingType.CLEAR } : (opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined),
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [new TextRun({ text: t, bold: !!opts.head || !!opts.bold, size: opts.head ? 21 : 20, color: opts.head ? "FFFFFF" : (opts.color || undefined) })] })]
  });
}
function table(widths, rows, opts){
  opts = opts || {};
  return new Table({
    width: { size: widths.reduce((a,b)=>a+b,0), type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({
      cantSplit: true,
      tableHeader: i === 0 && !opts.noHead,
      children: r.map((c, j) => cell(c, widths[j], { head: i === 0 && !opts.noHead, fill: i > 0 && i % 2 === 0 ? "F5F8FB" : undefined, bold: opts.firstColBold && j === 0 }))
    }))
  });
}
function spacer(){ return new Paragraph({ spacing: { after: 100 }, children: [] }); }

const kids = [];

// ============ 封面 ============
kids.push(new Paragraph({ spacing: { before: 2400, after: 200 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "geoconvert 三维模型转换器", bold: true, size: 56 })] }));
kids.push(new Paragraph({ spacing: { after: 2400 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "使 用 手 册", bold: true, size: 40, color: "1B4F72" })] }));
kids.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "OBJ · OSGB · TIF  →  3D Tiles", size: 28, color: "5D6D7E" })] }));
kids.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 },
  children: [new TextRun({ text: "五步流程版 · 2026 年 9 月", size: 22, color: "5D6D7E" })] }));
kids.push(new Paragraph({ children: [new PageBreak()] }));

// ============ 1 开始之前 ============
kids.push(h1("一、开始之前：安装、启动、认界面"));
kids.push(h2("1.1 安装与启动"));
kids.push(bulletB("安装：", "双击 geoconvert-setup-1.1.0.exe，一路「下一步」。不需要管理员权限，自动创建桌面和开始菜单快捷方式。"));
kids.push(bulletB("启动：", "双击快捷方式，打开一个全屏操作窗口。关闭窗口即退出程序。"));
kids.push(h2("1.2 认识界面：左侧四个页签"));
kids.push(p("整个软件只有 4 个页签，本手册的五步流程会在它们之间切换："));
kids.push(...img("m0-sidebar.png", "图 1  主界面：① 模型转换（上传并转换）② 坐标转换（拿经纬度）③ 3D 预览（微调位置）④ 注册模型（登记进系统）"));
kids.push(spacer());
kids.push(p("五步主线一句话：", { bold: true }));
kids.push(p("① 选类型、上传模型 → ② 拿经纬度填入 → ③ 选导出目录 → ④ 开始转换 + 注册 → ⑤ 位置不对就 3D 预览微调、保存、再注册。"));

// ============ 2 五步流程 ============
kids.push(new Paragraph({ children: [new PageBreak()] }));
kids.push(h1("二、五步转换流程（照着做就行）"));

// ---- 第 1 步 ----
kids.push(h2("第 1 步  选择模型类型，上传模型文件夹"));
kids.push(step("s1", "在「模型转换」页点格式卡片选择类型：OBJ / OSGB / TIF（选完输入文件后软件也会自动识别，一般不用手动点）。"));
kids.push(step("s1", "点输入框右侧「浏览…」，选择模型："));
kids.push(bullet("OBJ：选 .obj 文件；如果是多分块模型（一堆 Block 文件夹），直接选它们所在的根目录，一次全转；"));
kids.push(bullet("OSGB：选数据目录（里面应有 Data 文件夹和 metadata.xml）；"));
kids.push(bullet("TIF：选单个 .tif 影像文件。"));
kids.push(...img("m1-fmt-input.png", "图 2  第 1 步：① 点格式卡片选择 OBJ / OSGB / TIF；② 点「浏览…」上传模型文件或文件夹"));
kids.push(step("s1", "浏览弹层里：双击进入文件夹，选中模型后点「选择此项」；多分块模型进入根目录后直接点「选择当前目录」。需要新目录时点右上角「＋ 新建文件夹」现场创建。"));
kids.push(...img("m2-browse-dir.png", "图 3  浏览弹层：① 列表里是 8 个 Block 文件夹（多分块根目录）；② 点「选择当前目录」整个上传；③ 需要新建目录时点「＋ 新建文件夹」"));

// ---- 第 2 步 ----
kids.push(h2("第 2 步  没有经纬度？先去地图网站拿位置"));
kids.push(p("模型要摆到地球上的正确位置，需要 WGS-84 经纬度。OSGB 倾斜摄影通常自带坐标（metadata.xml），可跳过本步；OBJ 和 TIF 一般需要手动拿坐标。"));
kids.push(step("s2", "在地图网站（高德 / 百度 / 腾讯 / 必应）找到模型所在位置，点「分享」复制链接。"));
kids.push(step("s2", "切到「坐标转换」页签，把链接粘贴进「位置」框，点「解析」。"));
kids.push(step("s2", "结果区立即显示 WGS-84 经纬度（经度在前）。"));
kids.push(step("s2", "点「填入 OBJ/OSGB 定位」，坐标自动填进转换表单并切回转换页（TIF 模型改点「填入 TIF 中心」）。"));
kids.push(...img("m3-coord.png", "图 4  第 2 步：① 粘贴地图分享链接；② 点「解析」；③ 得到 WGS-84 经纬度；④ 点「填入 OBJ/OSGB 定位」自动填入转换表单"));
kids.push(p("两种特殊情况：", { bold: true }));
kids.push(bullet("手里只有坐标数字（如 103.05,25.50）：直接粘贴，并在下拉框选对坐标系——高德/腾讯坐标选 GCJ-02、百度选 BD-09、GPS 设备选 WGS-84。"));
kids.push(bullet("实在拿不到坐标：可以先留空直接转换，模型会先落在赤道，之后用第 5 步的 3D 预览拖到正确位置。"));

// ---- 第 3 步 ----
kids.push(h2("第 3 步  选择导出目录"));
kids.push(step("s3", "回到「模型转换」页，点输出框右侧「浏览…」，选一个空目录存放转换产物（tileset.json + b3dm 文件）。"));
kids.push(step("s3", "没有现成目录就点弹层右上角「＋ 新建文件夹」（见图 3 ③）现场建一个，建议命名如 D:\\模型转换\\排土场20260803。"));
kids.push(...img("m4-output-start.png", "图 5  第 3 步就绪状态：① 输出行点「浏览…」选导出目录；② 纬度/经度已由第 2 步自动填入；③ 一切就绪，点「开始转换」"));

// ---- 第 4 步 ----
kids.push(h2("第 4 步  开始转换，然后注册"));
kids.push(step("s4", "点「开始转换」（图 5 ③），下方日志开始滚动。"));
kids.push(step("s4", "日志最后一行出现「完成：用时 XXs，输出目录已就绪」、右上角状态变「完成」即成功（大模型转换时间较长，耐心等待；中途可点「取消」）。"));
kids.push(...img("m5-done.png", "图 6  第 4 步转换完成：① 日志最后一行「完成：用时…」；② 右上角状态「完成」"));
kids.push(step("s4", "转换成功后注册进系统：切到「注册模型」页签（或点底部快捷入口「注册到 models.json」）。"));
kids.push(step("s4", "点「自动探测」找到系统配置文件 models.json。"));
kids.push(step("s4", "填两项：目录名（英文，如 paiduichang）和显示名称（中文，如「排土场 2026-08」）；产物目录已自动填好。"));
kids.push(step("s4", "点「注册模型」。提示注册成功后，主系统刷新页面即可看到新模型。"));
kids.push(...img("m6-register.png", "图 7  注册模型：① 点「自动探测」找配置文件；② 填英文目录名；③ 填中文显示名称；④ 点「注册模型」"));
kids.push(p("如果此时预览发现模型位置不对，先别急——继续第 5 步微调，保存后再注册一次即可（同一 ID 重复注册 = 自动覆盖更新）。"));

// ---- 第 5 步 ----
kids.push(h2("第 5 步  位置不对？3D 预览微调后保存，再注册"));
kids.push(step("s5", "点「3D 预览」页签（或底部快捷入口「3D 预览与三轴调整」），产物目录已自动填好，点「打开 3D 预览」。"));
kids.push(step("s5", "把透明度滑块拉到 50% 左右，让模型半透明叠在卫星底图上，方便对位。"));
kids.push(step("s5", "拖拽模型上的彩色控件微调位置（见下表），也可在数值面板直接输入米数/角度。"));
kids.push(table([2600, 3200, 3600], [
  ["控件", "操作", "效果"],
  ["红/绿/蓝箭头", "按住拖动", "沿东/北/上方向平移模型"],
  ["彩色圆环", "按住拖动", "绕轴旋转模型"],
  ["轴上小方块", "按住拖动", "单独拉伸该轴缩放"],
  ["半透明彩色块", "按住拖动", "在两轴平面内斜向移动"],
  ["任何控件", "悬停时滚动滚轮", "0.01 米微调，精确对位"],
]));
kids.push(spacer());
kids.push(step("s5", "对准后把透明度拉回 100% 检查效果，点「保存（烘焙）」——调整值写进 tileset.json（原文件自动备份为 tileset.json.bak）。"));
kids.push(...img("m7-preview.png", "图 8  第 5 步 3D 预览：① 拖拽三轴控件微调模型位置；② 透明度滑块（半透明便于与底图对齐）；③ 调好后点「保存（烘焙）」"));
kids.push(step("s5", "回「注册模型」页再注册一次（目录名、显示名称照旧），系统里即为最终位置。完成！"));

// ============ 3 格式差异 ============
kids.push(new Paragraph({ children: [new PageBreak()] }));
kids.push(h1("三、三种格式差异速查"));
kids.push(table([1300, 3100, 2700, 2300], [
  ["格式", "输入选什么", "定位怎么给", "额外要填"],
  ["OBJ", ".obj 文件，或多分块根目录（整夹上传）", "经纬度（第 2 步获取）；或选「参考 tileset」与已有模型重合", "无"],
  ["OSGB", "数据目录（含 Data\\*.osgb + metadata.xml）", "通常不用填——自动读 metadata.xml；文件缺失才手填", "无"],
  ["TIF", "单个 .tif 影像文件", "「中心」填 经度,纬度（第 2 步点「填入 TIF 中心」）", "宽度（影像东西向真实地面米数）；离地高度默认 0.1"],
]));
kids.push(spacer());
kids.push(p("怎么确认目录选对了？", { bold: true }));
kids.push(bullet("OBJ 多分块：选中的目录里应是一堆 Block* 文件夹（每个里面一个 .obj + 贴图）。"));
kids.push(bullet("OSGB：选中的目录里应有 Data 文件夹和 metadata.xml。只看到一堆 Tile_ 文件夹说明层级选错了，退一级再选。"));
kids.push(bullet("TIF：认准单个 .tif / .tiff 文件，另需准备中心坐标和地面宽度。"));

// ============ 4 常见问题 ============
kids.push(h1("四、常见问题与排查（出问题先看这里）"));
kids.push(table([2800, 3300, 3260], [
  ["现象 / 报错", "原因", "解决办法"],
  ["日志报 unrecognized arguments: --lat … --lon（TIF 转换）", "旧版本 bug：纬度/经度残留值被误传给 tif 命令", "新版已修复。若还遇到，清空纬度/经度两栏再转换，或重装最新安装包"],
  ["输入路径不存在", "手输路径错误，或文件被移动/删除", "点「浏览…」重新选择；检查盘符"],
  ["OBJ 目录内未找到 .obj 文件", "选错了层级，目录里没有 .obj", "选到真正装 .obj 的那一级（多分块选 Block* 文件夹的父目录），或直接选具体 .obj 文件"],
  ["OSGB 输入应为数据目录", "OSGB 模式选了单个文件或选错层级", "选包含 Data\\*.osgb 和 metadata.xml 的那一级文件夹"],
  ["请填写影像中心经纬度 / 地面宽度", "TIF 模式中心或宽度栏为空", "中心填 lon,lat（用第 2 步「填入 TIF 中心」）；宽度填影像东西向真实地面米数"],
  ["经纬度/中心必须是数字", "填了汉字、多逗号或度分秒格式", "用十进制度小数，如 116.3"],
  ["注册时提示目标目录存在但无 tileset.json，拒绝覆盖", "防误删保护", "换个目录名；或确认目录内容后手动清空再注册"],
  ["预览打不开，提示无 tileset.json", "产物目录选错", "选转换输出的目录（能看到 tileset.json 的那层）"],
  ["预览里模型在赤道非洲附近", "转换时定位留空（预期行为，不是 bug）", "用第 5 步拖拽微调，或在数值面板直接输入平移量（X 东 / Y 北 / Z 上，单位米）"],
  ["TIF 预览黑底不透明", "旧版本产物材质无透明通道", "用新版重新转换一次"],
  ["预览地图没有中文地名", "天地图注记层需要联网", "检查网络；离线时仅无地名，不影响功能"],
  ["双击 exe 无反应或闪退", "杀软拦截 / 缺 WebView2", "加白名单重试；会自动回退浏览器模式"],
  ["保存烘焙后想反悔", "需要撤销位置调整", "输出目录里的 tileset.json.bak 是烘焙前备份，改名回 tileset.json 即可还原"],
]));
kids.push(spacer());
kids.push(p("判断成功只需看一处：日志最后出现「完成：用时…」。中途「失败: 退出码 N」则往上翻日志找第一条 error，对照上表处理。"));

// ============ 5 附录 ============
kids.push(h1("五、附录"));
kids.push(h2("5.1 命令行用法（进阶，可跳过）"));
kids.push(code("geoconvert.exe obj  <输入.obj 或多分块根目录> <输出目录> [--lat 纬度 --lon 经度] [--height 0] [--max-tris 250000]\ngeoconvert.exe osgb <数据目录> --out <输出目录> [--lat … --lon …]\ngeoconvert.exe tif  <输入.tif> <输出目录> --center lon,lat --width 米 [--format png] [--height 0.1]"));
kids.push(h2("5.2 关键路径"));
kids.push(table([3200, 6160], [
  ["东西", "位置"],
  ["软件安装目录", "C:\\Users\\<用户名>\\AppData\\Local\\Programs\\geoconvert"],
  ["系统模型根目录", "D:\\WEB\\zicaiduck\\www\\public\\（各模型一个子目录）"],
  ["模型清单", "www\\public\\terra_b3dms\\models.json（注册页「自动探测」找的就是它）"],
  ["烘焙备份", "输出目录里的 tileset.json.bak（保存前的原始版本）"],
]));

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: F, size: 22 } }
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, color: "1B4F72", font: F },
        paragraph: { spacing: { before: 280, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, color: "21618C", font: F },
        paragraph: { spacing: { before: 220, after: 140 }, outlineLevel: 1 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 620, hanging: 300 } } } }] },
      ...["s1", "s2", "s3", "s4", "s5"].map(ref => ({
        reference: ref,
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 640, hanging: 360 } }, run: { bold: true, color: "1B4F72" } } }]
      })),
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1200, right: 1200, bottom: 1200, left: 1200 }
      }
    },
    headers: {
      default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "geoconvert 使用手册 · 五步流程版", size: 16, color: "8899AA" })] })] })
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "第 ", size: 16, color: "8899AA" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "8899AA" }), new TextRun({ text: " 页", size: 16, color: "8899AA" })] })] })
    },
    children: kids
  }]
});

const OUT = process.argv[2] || "geoconvert使用手册.docx";
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log("OK", OUT, buf.length, "bytes");
});
