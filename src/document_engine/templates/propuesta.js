const { Document, Packer, Paragraph, TextRun } = require('docx');
const fs = require('fs');
const path = require('path');
const { buildCoverPage } = require('../cover');
const { buildPageHeader, buildPageFooter } = require('../header_footer');

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error("Uso: node propuesta.js '<json_payload>' <output_path>");
  process.exit(1);
}

const payload = JSON.parse(args[0]);
const outputPath = args[1];

// Asegurar que docType sea correcto para la propuesta
payload.docType = 'PROPUESTA COMERCIAL';

const doc = new Document({
  sections: [
    {
      properties: {},
      children: buildCoverPage(payload),
    },
    {
      properties: {
        page: {
          pageNumbers: { start: 1, formatType: "DECIMAL" }
        }
      },
      headers: buildPageHeader(payload),
      footers: buildPageFooter(payload),
      children: [
        new Paragraph({
          spacing: { before: 240, after: 120 },
          children: [
            new TextRun({
              text: 'Estimado/a ',
              font: 'Inter',
              size: 24,
            }),
            new TextRun({
              text: payload.client_name || 'Cliente',
              font: 'Inter',
              size: 24,
              bold: true,
            }),
            new TextRun({
              text: ',',
              font: 'Inter',
              size: 24,
            }),
          ]
        }),
        new Paragraph({
          spacing: { before: 120, after: 120 },
          children: [
            new TextRun({
              text: `En Evangelista & Co. hemos analizado detenidamente los requerimientos para el proyecto "${payload.project_name || 'Proyecto'}" y presentamos a continuación nuestra propuesta comercial para atender sus necesidades con la máxima excelencia.`,
              font: 'Inter',
              size: 24,
            }),
          ]
        }),
        new Paragraph({
          spacing: { before: 240, after: 120 },
          children: [
            new TextRun({
              text: 'Resumen Financiero',
              font: 'Instrument Serif',
              size: 36,
              bold: true,
              color: payload.accentColor ? payload.accentColor.replace('#', '') : 'C05538',
            })
          ]
        }),
        new Paragraph({
          spacing: { before: 120, after: 120 },
          children: [
            new TextRun({
              text: `Inversión Base: $${payload.base_price ? payload.base_price.toLocaleString('es-MX') : '0.00'} MXN`,
              font: 'Inter',
              size: 24,
            })
          ]
        }),
        new Paragraph({
          spacing: { before: 0, after: 120 },
          children: [
            new TextRun({
              text: `Total antes de impuestos: $${payload.total_before_tax ? payload.total_before_tax.toLocaleString('es-MX') : '0.00'} MXN`,
              font: 'Inter',
              size: 24,
            })
          ]
        }),
        new Paragraph({
          spacing: { before: 0, after: 120 },
          children: [
            new TextRun({
              text: `Total con impuestos: $${payload.total_with_tax ? payload.total_with_tax.toLocaleString('es-MX') : '0.00'} MXN`,
              font: 'Inter',
              size: 24,
              bold: true,
            })
          ]
        }),
        new Paragraph({
          spacing: { before: 480, after: 120 },
          children: [
            new TextRun({
              text: 'Atentamente,',
              font: 'Inter',
              size: 24,
            })
          ]
        }),
        new Paragraph({
          spacing: { before: 120, after: 0 },
          children: [
            new TextRun({
              text: payload.signer_name || 'Adriel Evangelista',
              font: 'Inter',
              size: 24,
              bold: true,
            })
          ]
        }),
        new Paragraph({
          spacing: { before: 0, after: 0 },
          children: [
            new TextRun({
              text: payload.signer_role || 'Director General',
              font: 'Inter',
              size: 24,
            })
          ]
        }),
      ]
    }
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outputPath, buffer);
  console.log(`Documento generado en ${outputPath}`);
}).catch(err => {
  console.error("Error generando docx:", err);
  process.exit(1);
});
