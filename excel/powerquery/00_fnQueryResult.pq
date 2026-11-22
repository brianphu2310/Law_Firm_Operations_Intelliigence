// Query name: fnQueryResult   (a function: paste first, the other queries call it)
// Reads one SQL result (docs/query_results/<name>.csv) or one warehouse table (data/warehouse/<name>.csv) straight from GitHub.
// Excel: Data > Get Data > From Other Sources > Blank Query > Advanced Editor > paste > Done > rename to fnQueryResult.
let
    Base = "https://raw.githubusercontent.com/brianphu2310/law-firm-decision-support/main/",
    fn = (folder as text, name as text) as table =>
        let
            Source   = Csv.Document(Web.Contents(Base, [RelativePath = folder & "/" & name & ".csv"]), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
            Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
        in
            Promoted
in
    fn
