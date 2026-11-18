// Power Query straight against the (mock) MYOB API: OAuth token, MYOB headers, and following NextPageLink until every page
// is read, then flattening the nested Customer / Salesperson / Category / Lines records. No Python involved.
// Live MYOB: change BaseUrl to https://api.myob.com and use an access token from the MYOB OAuth sign-in (never paste secrets
// into a shared workbook: keep them in a parameter or Excel's data source credentials).
let
    BaseUrl  = "http://127.0.0.1:8000",
    ClientId = "mock-client-id",
    Secret   = "mock-client-secret",

    Token = Json.Document(Web.Contents(BaseUrl, [
                RelativePath = "oauth/token",
                Headers = [#"Content-Type" = "application/x-www-form-urlencoded"],
                Content = Text.ToBinary("grant_type=client_credentials&client_id=" & ClientId & "&client_secret=" & Secret)]))[access_token],
    Headers = [Authorization = "Bearer " & Token, #"x-myobapi-key" = ClientId, #"x-myobapi-version" = "v2"],

    CompanyFile = Json.Document(Web.Contents(BaseUrl, [RelativePath = "accountright/", Headers = Headers])){0},
    GetPage = (skip as number) => Json.Document(Web.Contents(BaseUrl, [
                RelativePath = "accountright/" & CompanyFile[Id] & "/Sale/Invoice/Service",
                Query = [#"$top" = "400", #"$skip" = Number.ToText(skip)], Headers = Headers])),
    Pages = List.Generate(
                () => [skip = 0, page = GetPage(0)],
                each List.Count([page][Items]) > 0,
                each [skip = [skip] + 400, page = if [page][NextPageLink] = null then [Items = {}] else GetPage([skip] + 400)],
                each [page][Items]),

    Invoices  = Table.FromRecords(List.Combine(Pages)),
    Customer  = Table.ExpandRecordColumn(Invoices, "Customer", {"Name", "DisplayID"}, {"Client", "ClientCode"}),
    Attorney  = Table.ExpandRecordColumn(Customer, "Salesperson", {"Name"}, {"Attorney"}),
    Branch    = Table.ExpandRecordColumn(Attorney, "Category", {"Name"}, {"Branch"}),
    Terms     = Table.ExpandRecordColumn(Branch, "Terms", {"DueDate"}, {"DueDate"}),
    Area      = Table.AddColumn(Terms, "PracticeArea", each [Lines]{0}[Job][Name], type text),
    Selected  = Table.SelectColumns(Area, {"Number", "Date", "DueDate", "Client", "ClientCode", "PracticeArea", "Attorney", "Branch",
                                           "Subtotal", "TotalTax", "TotalAmount", "BalanceDueAmount", "Status"}),
    Typed     = Table.TransformColumnTypes(Selected, {{"Date", type datetime}, {"DueDate", type datetime},
                    {"Subtotal", Currency.Type}, {"TotalTax", Currency.Type}, {"TotalAmount", Currency.Type}, {"BalanceDueAmount", Currency.Type}})
in
    Typed
