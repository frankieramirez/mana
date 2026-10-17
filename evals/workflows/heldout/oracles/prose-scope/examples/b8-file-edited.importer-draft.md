# Importer, draft release note

Starting with version 4.2, the importer brings in every record that passes schema validation. Records that fail validation aren't imported and are listed in the rejection report; a future `posted_on` date is one example. The importer doesn't modify records.
