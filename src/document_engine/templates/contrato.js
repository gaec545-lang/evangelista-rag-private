const { Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow, TableCell, WidthType, BorderStyle } = require('docx');
const fs = require('fs');
const { buildCoverPage } = require('../cover');
const { buildPageHeader, buildPageFooter } = require('../header_footer');

const args = process.argv.slice(2);
const payload = JSON.parse(args[0]);
const outputPath = args[1];

payload.docType = 'CONTRATO MAESTRO DE SERVICIOS';
const accent = (payload.accentColor || '#3e4d32').replace('#', '');

const doc = new Document({
  sections: [
    { children: buildCoverPage(payload) },
    {
      headers: buildPageHeader(payload),
      footers: buildPageFooter(payload),
      children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 240, after: 480 },
          children: [
            new TextRun({
              text: 'CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES',
              font: 'Times New Roman',
              size: 28,
              bold: true,
              color: accent,
            })
          ]
        }),
        new Paragraph({
          spacing: { before: 120, after: 120 },
          alignment: AlignmentType.JUSTIFY,
          children: [
            new TextRun({
              text: 'El presente Contrato Maestro de Servicios establece los términos y condiciones legales bajo los cuales ',
              font: 'Inter',
              size: 20,
            }),
            new TextRun({
              text: 'Evangelista & Co.',
              font: 'Inter',
              size: 20,
              bold: true,
            }),
            new TextRun({
              text: ' ("Prestador") brindará servicios especializados de arquitectura de inteligencia a ',
              font: 'Inter',
              size: 20,
            }),
            new TextRun({
              text: payload.client_name || 'El Cliente',
              font: 'Inter',
              size: 20,
              bold: true,
            }),
            new TextRun({
              text: ' ("Cliente").',
              font: 'Inter',
              size: 20,
            }),
          ]
        }),

        new Paragraph({
          spacing: { before: 240, after: 120 },
          children: [new TextRun({ text: 'I. CONDICIONES ECONÓMICAS', font: 'Inter', size: 22, bold: true, color: '666666' })]
        }),

        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          rows: [
            new TableRow({
              children: [
                new TableCell({ 
                  shading: { fill: 'F5F5F7' },
                  children: [new Paragraph({ children: [new TextRun({ text: 'Hito de Pago', font: 'Inter', size: 18, bold: true })] })] 
                }),
                new TableCell({ 
                  shading: { fill: 'F5F5F7' },
                  children: [new Paragraph({ children: [new TextRun({ text: 'Monto Estimado (MXN)', font: 'Inter', size: 18, bold: true })] })] 
                }),
              ]
            }),
            new TableRow({
              children: [
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: 'Setup Fee / Anticipo Operativo', font: 'Inter', size: 18 })] })] }),
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: `$${(payload.variables?.setup_fee || 0).toLocaleString()}`, font: 'Inter', size: 18, bold: true })] })] }),
              ]
            }),
            new TableRow({
              children: [
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: 'Fase de Ejecución e Inteligencia', font: 'Inter', size: 18 })] })] }),
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: `$${(payload.variables?.base_price || 0).toLocaleString()}`, font: 'Inter', size: 18, bold: true })] })] }),
              ]
            })
          ]
        }),

        new Paragraph({
          spacing: { before: 240, after: 120 },
          children: [new TextRun({ text: 'II. ALCANCE Y METODOLOGÍA', font: 'Inter', size: 22, bold: true, color: '666666' })]
        }),
        new Paragraph({
          spacing: { before: 120, after: 120 },
          alignment: AlignmentType.JUSTIFY,
          children: [
            new TextRun({
              text: 'Los entregables técnicos, cronogramas y KPIs se rigen por la Propuesta de Arquitectura aceptada con folio ',
              font: 'Inter',
              size: 20,
            }),
            new TextRun({
              text: payload.proposal_folio || 'Vigente',
              font: 'Inter',
              size: 20,
              bold: true,
              color: accent,
            }),
            new TextRun({
              text: '. El Prestador se compromete a una ejecución bajo los estándares ALCOA+ de integridad de datos.',
              font: 'Inter',
              size: 20,
            }),
          ]
        }),

        new Paragraph({
          spacing: { before: 480, after: 120 },
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: 'ACEPTACIÓN DE TÉRMINOS', font: 'Inter', size: 18, bold: true, color: '999999' })]
        }),

        new Paragraph({
          spacing: { before: 960, after: 120 },
          children: [
            new TextRun({ text: '__________________________          __________________________', font: 'Inter', size: 20 }),
          ]
        }),
        new Paragraph({
          children: [
            new TextRun({ text: '        Adriel Evangelista                              Por El Cliente', font: 'Inter', size: 18, bold: true }),
          ]
        }),
        new Paragraph({
          children: [
            new TextRun({ text: '        Director General                                Representante Legal', font: 'Inter', size: 16, color: '666666' }),
          ]
        }),
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => fs.writeFileSync(outputPath, buffer));
