const { Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow, TableCell, WidthType } = require('docx');
const fs = require('fs');
const { buildCoverPage } = require('../cover');
const { buildPageHeader, buildPageFooter } = require('../header_footer');

const args = process.argv.slice(2);
const payload = JSON.parse(args[0]);
const outputPath = args[1];

payload.docType = 'ORDEN DE SERVICIO (OS)';
const accent = (payload.accentColor || '#534ab7').replace('#', '');

const doc = new Document({
  sections: [
    { children: buildCoverPage(payload) },
    {
      headers: buildPageHeader(payload),
      footers: buildPageFooter(payload),
      children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 240, after: 360 },
          children: [
            new TextRun({
              text: 'ORDEN DE SERVICIO OPERATIVA',
              font: 'Instrument Serif',
              size: 32,
              bold: true,
              color: accent,
            })
          ]
        }),
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          rows: [
            new TableRow({
              children: [
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: 'Responsable', font: 'Inter', size: 20, bold: true })] })] }),
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: payload.responsible_name || 'N/A', font: 'Inter', size: 20 })] })] }),
              ]
            }),
            new TableRow({
              children: [
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: 'Workstream', font: 'Inter', size: 20, bold: true })] })] }),
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: payload.workstream_name || 'General', font: 'Inter', size: 20 })] })] }),
              ]
            }),
            new TableRow({
              children: [
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: 'Objetivo', font: 'Inter', size: 20, bold: true })] })] }),
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: payload.objective || 'Ejecución técnica', font: 'Inter', size: 20 })] })] }),
              ]
            })
          ]
        }),
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => fs.writeFileSync(outputPath, buffer));
