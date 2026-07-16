"""
API views for floor plan upload, processing, and layout saving.
"""

import json
import os

from django.conf import settings
from django.http import JsonResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .opencv_service import process_floorplan


class UploadFloorPlanView(APIView):
    """
    POST /api/upload-floorplan/

    Accepts a floor plan image, runs OpenCV processing, and returns
    detected room polygons.
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        image_file = request.FILES.get('image')

        if not image_file:
            return Response(
                {"error": "No image file provided. Send an 'image' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml']
        if image_file.content_type not in allowed_types:
            return Response(
                {"error": f"Unsupported file type: {image_file.content_type}. Use PNG, JPG, or SVG."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            image_bytes = image_file.read()
            result = process_floorplan(image_bytes)

            # Save the uploaded image so the frontend can display it
            media_dir = os.path.join(settings.MEDIA_ROOT, 'floorplans')
            os.makedirs(media_dir, exist_ok=True)

            if image_file.content_type == 'image/svg+xml':
                image_path = os.path.join(media_dir, 'latest_floorplan.svg')
            else:
                image_path = os.path.join(media_dir, 'latest_floorplan.png')

            with open(image_path, 'wb') as f:
                f.write(image_bytes)

            result['image_url'] = f'/media/floorplans/{os.path.basename(image_path)}'
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"Processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SaveLayoutView(APIView):
    """
    POST /api/save-layout/

    Saves the current room layout (polygons + names) to a JSON file.
    """

    def post(self, request):
        rooms = request.data.get('rooms')

        if rooms is None:
            return Response(
                {"error": "No 'rooms' field in request body."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            save_dir = os.path.join(settings.MEDIA_ROOT, 'layouts')
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, 'saved_layout.json')

            with open(save_path, 'w') as f:
                json.dump({"rooms": rooms}, f, indent=2)

            return Response(
                {"message": "Layout saved successfully.", "path": save_path},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to save layout: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LoadLayoutView(APIView):
    """
    GET /api/load-layout/

    Loads the previously saved room layout from JSON.
    """

    def get(self, request):
        save_path = os.path.join(settings.MEDIA_ROOT, 'layouts', 'saved_layout.json')

        if not os.path.exists(save_path):
            return Response(
                {"error": "No saved layout found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            with open(save_path, 'r') as f:
                data = json.load(f)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Failed to load layout: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
