// Builds the Word guide from SETUP_GUIDE.md so both stay identical.
// usage: node scripts/build_setup_guide.js SETUP_GUIDE.md Instagram_MCP_Setup_Guide.docx   (needs: npm install docx)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
  ShadingType, HeadingLevel, AlignmentType, LevelFormat, BorderStyle, Footer,
  PageNumber, ImageRun,
} = require("docx");

const [, , source, target] = process.argv;
if (!source || !target || !source.endsWith(".md") || !target.endsWith(".docx")) {
  console.error("usage: node scripts/build_setup_guide.js <guide.md> <out.docx>");
  process.exit(1);
}

const FONT = "Arial";
const MONO = "Menlo";
const ACCENT = "1F4E79";
const CONTENT_WIDTH = 9026; // A4 with 1-inch margins

// Inline markup: **bold** and `code`
function runs(text, base = {}) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean).map((part) => {
    if (part.startsWith("**")) return new TextRun({ ...base, text: part.slice(2, -2), bold: true });
    if (part.startsWith("`")) return new TextRun({ ...base, text: part.slice(1, -1), font: MONO, size: 19 });
    return new TextRun({ ...base, text: part });
  });
}

const h1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
const h2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
const p = (text) => new Paragraph({ spacing: { after: 140 }, children: runs(text) });
const bullet = (text, level) =>
  new Paragraph({ numbering: { reference: "bullets", level }, spacing: { after: 70 }, children: runs(text) });
const step = (text, instance) =>
  new Paragraph({ numbering: { reference: "steps", level: 0, instance }, spacing: { after: 90 }, children: runs(text) });
const code = (text, indented) =>
  new Paragraph({
    spacing: { before: 60, after: 160 },
    indent: { left: indented ? 560 : 200, right: 200 },
    shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
    children: [new TextRun({ text, font: MONO, size: 18 })],
  });

function note(text) {
  const danger = text.startsWith("**Important");
  return new Paragraph({
    spacing: { before: 120, after: 200 },
    indent: { left: 200, right: 200 },
    shading: { type: ShadingType.CLEAR, fill: danger ? "FDE9E7" : "FFF4D6" },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: danger ? "C0392B" : "E0A800", space: 8 } },
    children: runs(text),
  });
}

function table(header, rows) {
  const wide = ["Setting", "Tool"].includes(header[0]);
  const widths = header.length === 2 ? [3700, 5326] : wide ? [3500, 3726, 1800] : [3000, 4126, 1900];
  const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (text, i, isHeader) =>
    new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      borders,
      margins: { top: 70, bottom: 70, left: 110, right: 110 },
      shading: isHeader ? { type: ShadingType.CLEAR, fill: "DCE6F1" } : undefined,
      children: [new Paragraph({ children: runs(text, isHeader ? { bold: true } : {}) })],
    });
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: header.map((t, i) => cell(t, i, true)) }),
      ...rows.map((r) => new TableRow({ children: r.map((t, i) => cell(t, i, false)) })),
    ],
  });
}

// Read a JPEG's pixel size from its start-of-frame marker
function jpegSize(data) {
  let i = 2;
  while (i < data.length) {
    const marker = data[i + 1];
    const length = data.readUInt16BE(i + 2);
    if (marker >= 0xc0 && marker <= 0xc3) return { height: data.readUInt16BE(i + 5), width: data.readUInt16BE(i + 7) };
    i += 2 + length;
  }
  throw new Error("not a JPEG with a size marker");
}

function image(file) {
  const data = fs.readFileSync(file);
  const size = jpegSize(data);
  const width = 600; // text width
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 60 },
    border: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 2 },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 2 },
      left: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 2 },
      right: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 2 },
    },
    children: [new ImageRun({ type: "jpg", data, transformation: { width, height: Math.round(width * size.height / size.width) } })],
  });
}
const caption = (text) =>
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({ text, italics: true, size: 18, color: "595959" })],
  });

const splitRow = (line) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

function convert(markdown) {
  const out = [];
  const lines = markdown.split("\n");
  let listInstance = 0;
  let inCode = false;
  let codeIndented = false;

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.trim();

    if (line.startsWith("```")) {
      inCode = !inCode;
      codeIndented = raw.startsWith("   ");
      continue;
    }
    if (inCode) { out.push(code(line, codeIndented)); continue; }
    if (!line || line === "---") continue;

    if (line.startsWith("# ")) {
      const [kind, subject] = line.slice(2).split(": ");
      out.push(new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: subject || kind, bold: true, size: 40, color: ACCENT })],
      }));
      out.push(new Paragraph({
        spacing: { after: 240 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 6 } },
        children: [new TextRun({ text: subject ? kind + ", written for non-technical users" : "", size: 26, color: "595959" })],
      }));
    } else if (line.startsWith("## ")) {
      listInstance += 1;
      out.push(h1(line.slice(3)));
    } else if (line.startsWith("### ")) {
      listInstance += 1;
      out.push(h2(line.slice(4)));
    } else if (line.startsWith("|")) {
      const header = splitRow(line);
      const rows = [];
      i += 1; // separator row
      while (i + 1 < lines.length && lines[i + 1].trim().startsWith("|")) rows.push(splitRow(lines[++i]));
      out.push(table(header, rows));
      out.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
    } else if (/^!\[.*\]\(.+\)$/.test(line)) {
      out.push(image(path.join(path.dirname(source), line.match(/\((.+)\)$/)[1])));
    } else if (/^\*[^*].*\*$/.test(line)) {
      out.push(caption(line.slice(1, -1)));
    } else if (line.startsWith("> ")) {
      out.push(note(line.slice(2)));
    } else if (line.startsWith("- ")) {
      out.push(bullet(line.slice(2), raw.startsWith("   ") ? 1 : 0));
    } else if (/^\d+\. /.test(line)) {
      if (line.startsWith("1. ")) listInstance += 1; // a list that starts at 1 restarts numbering
      out.push(step(line.replace(/^\d+\. /, ""), listInstance));
    } else {
      out.push(p(line));
    }
  }
  return out;
}

const doc = new Document({
  creator: "Ernest Rimkevicius",
  title: "Instagram and Facebook Assistant for Claude: Easy Setup Guide",
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 30, bold: true, color: ACCENT },
        paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, color: "262626" },
        paragraph: { spacing: { before: 260, after: 120 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [
          { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 560, hanging: 280 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1000, hanging: 280 } } } },
        ] },
      { reference: "steps",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 560, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: ["Page ", PageNumber.CURRENT], size: 17, color: "7F7F7F" })],
        })],
      }),
    },
    children: convert(fs.readFileSync(source, "utf8")),
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(target, buf);
  console.log("wrote", target, buf.length, "bytes");
});
