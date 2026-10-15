import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from xml.dom import minidom


class VRAISOXMLService:
    """
    Gera ISO 11783-10 (ISO-XML) para prescrição VRA.
    Baseado em ISO 11783-10 Part 10: Task data exchange.
    """

    NAMESPACE = "http://www.iso11783.org/schemas/task_data_v4"
    XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

    @classmethod
    def generate_prescricao_xml(cls, prescricao) -> str:
        """Gera ISO-XML para uma PrescricaoVRA"""
        ns = {"iso": "http://www.iso11783.org/schemas/task_data_v4"}
        ET.register_namespace("", "http://www.iso11783.org/schemas/task_data_v4")
        ET.register_namespace("xsi", cls.XSI_NS)

        # Root element
        task_data = ET.Element(
            "{http://www.iso11783.org/schemas/task_data_v4}ISO11783_TaskData",
            {"versionMajor": "4", "versionMinor": "0"},
        )

        # Meta data
        meta = ET.SubElement(task_data, "MetaData")
        ET.SubElement(meta, "TaskControllerId").text = "AMPLIAGRO"
        ET.SubElement(meta, "ManufacturerId").text = "AMPLIAGRO"
        ET.SubElement(meta, "ProductName").text = "Prescrição VRA"
        ET.SubElement(meta, "Version").text = "1.0"
        ET.SubElement(meta, "CreationDate").text = datetime.now().isoformat()

        # Customer (propriedade)
        customer = ET.SubElement(task_data, "Customer")
        ET.SubElement(customer, "CustomerId").text = str(
            prescricao.safra.propriedade.id
        )
        ET.SubElement(customer, "Name").text = prescricao.safra.propriedade.nome

        # Farm (propriedade)
        farm = ET.SubElement(task_data, "Farm")
        ET.SubElement(farm, "FarmId").text = str(prescricao.safra.propriedade.id)
        ET.SubElement(farm, "Name").text = prescricao.safra.propriedade.nome
        ET.SubElement(farm, "CustomerRefId").text = str(prescricao.safra.propriedade.id)

        # Field (talhao)
        field = ET.SubElement(task_data, "Field")
        ET.SubElement(field, "FieldId").text = str(prescricao.talhao.id)
        ET.SubElement(field, "Name").text = prescricao.talhao.nome
        ET.SubElement(field, "FarmRefId").text = str(prescricao.safra.propriedade.id)

        # Crop Type (cultura)
        crop_type = ET.SubElement(task_data, "CropType")
        ET.SubElement(crop_type, "CropTypeId").text = str(prescricao.cultura.id)
        ET.SubElement(crop_type, "Name").text = prescricao.cultura.nome

        # Treatment (prescrição)
        treatment = ET.SubElement(task_data, "Treatment")
        ET.SubElement(treatment, "TreatmentId").text = str(prescricao.id)
        ET.SubElement(
            treatment, "Name"
        ).text = f"VRA {prescricao.cultura.nome} - {prescricao.tipo_insumo}"
        ET.SubElement(treatment, "CropTypeRefId").text = str(prescricao.cultura.id)
        ET.SubElement(treatment, "CustomerRefId").text = str(
            prescricao.safra.propriedade.id
        )

        # Product (insumo)
        if prescricao.insumo:
            product = ET.SubElement(task_data, "Product")
            ET.SubElement(product, "ProductId").text = str(prescricao.insumo.id)
            ET.SubElement(product, "Name").text = prescricao.insumo.nome
            ET.SubElement(product, "ProductType").text = prescricao.tipo_insumo
            ET.SubElement(product, "Unit").text = prescricao.unidade

        # Guidance (opcional - grade geojson)
        if prescricao.grade_geojson:
            guidance = ET.SubElement(task_data, "Guidance")
            ET.SubElement(guidance, "GuidanceId").text = f"GUID_{prescricao.id}"
            ET.SubElement(guidance, "Name").text = f"Grade VRA {prescricao.talhao.nome}"
            ET.SubElement(guidance, "FieldRefId").text = str(prescricao.talhao.id)

            # GeoJSON -> Partfield (simplificado - feature collection)
            for feat in prescricao.grade_geojson.get("features", []):
                partfield = ET.SubElement(guidance, "Partfield")
                ET.SubElement(partfield, "PartfieldId").text = str(
                    feat.get("properties", {}).get("cell_id", "")
                )
                ET.SubElement(partfield, "FieldRefId").text = str(prescricao.talhao.id)
                ET.SubElement(
                    partfield, "Name"
                ).text = f"Cell {feat.get('properties', {}).get('cell_id', '')}"

                # Value (dose_ha)
                dose = feat.get("properties", {}).get("dose_ha", prescricao.dose_ha)
                value_elem = ET.SubElement(partfield, "Value")
                ET.SubElement(value_elem, "ValueType").text = "ApplicationRate"
                ET.SubElement(value_elem, "Unit").text = prescricao.unidade
                ET.SubElement(value_elem, "Value").text = str(dose)

        # Pretty print
        rough_string = ET.tostring(task_data, encoding="unicode")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    @classmethod
    def save_xml_file(cls, prescricao) -> str:
        """Gera e salva o arquivo ISO-XML"""
        xml_content = cls.generate_prescricao_xml(prescricao)
        prescricao.iso_xml = xml_content
        # Salva no campo arquivo se quiser
        # from django.core.files.base import ContentFile
        # prescricao.arquivo_iso.save(f"vra_{prescricao.id}.xml", ContentFile(xml_content.encode("utf-8")))
        prescricao.save(update_fields=["iso_xml", "atualizado_em"])
        return xml_content
