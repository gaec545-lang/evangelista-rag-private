const { Header, Footer, Paragraph, TextRun, BorderStyle, PageNumber } = require('docx');

const buildPageHeader = (config) => {
  const { accentColor, folio, docType } = config;
  const accent = (accentColor || '#c05538').replace('#', '').toUpperCase();

  return {
    default: new Header({
      children: [
        new Paragraph({
          border: {
            bottom: {
              style: BorderStyle.SINGLE,
              size: 6,
              color: accent,
              space: 1,
            },
          },
          spacing: { before: 0, after: 120 },
          children: [
            new TextRun({
              text: 'EVANGELISTA & CO.',
              font: 'Inter',
              size: 16,
              color: '999999',
            }),
            new TextRun({
              text: `     ${docType || 'DOCUMENTO'}`,
              font: 'Inter',
              size: 16,
              color: '999999',
            }),
            new TextRun({
              text: `\t${folio || ''}`,
              font: 'Inter',
              size: 16,
              bold: true,
              color: accent,
            }),
          ],
        }),
      ],
    }),
  };
};

const buildPageFooter = (config) => {
  const { clientName, projectName } = config;

  return {
    default: new Footer({
      children: [
        new Paragraph({
          border: {
            top: {
              style: BorderStyle.SINGLE,
              size: 4,
              color: 'DDDDDD',
              space: 1,
            },
          },
          spacing: { before: 120, after: 0 },
          children: [
            new TextRun({
              text: `${clientName || ''} · ${projectName || ''}`,
              font: 'Inter',
              size: 16,
              color: 'AAAAAA',
            }),
            new TextRun({
              text: '\tPágina ',
              font: 'Inter',
              size: 16,
              color: 'AAAAAA',
            }),
            new TextRun({
              children: [PageNumber.CURRENT],
              font: 'Inter',
              size: 16,
              color: 'AAAAAA',
            }),
          ],
        }),
      ],
    }),
  };
};

module.exports = { buildPageHeader, buildPageFooter };
